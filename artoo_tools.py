# --- v2.1.0 Artoo Execution Tools (Node-Aware Dispatcher) ---
# Change Message:
# - v2.1.0: Patched the subprocess Spotify handoff. The target_node variable is now explicitly passed as sys.argv[2] to spotify_control.py, preventing the default "local" override bug. Added subprocess.STDOUT capture so Gemma can read playback errors.
# - v2.0.0: Refactored dispatcher to support 'target_node' routing for Home Assistant (tinytuya/kasa) and Spotify.

import subprocess
import json

def local_artoo_executor(command: str, target_node: str = "local") -> str:
    """
    Artoo's master execution router. 
    Takes a plain text command and a target hardware node from Gemma and routes it 
    to the correct local Python script or API.
    """
    command = command.lower().strip()
    
    # --- 1. SPOTIFY ROUTING ---
    if "play" in command or "stop" in command or "pause" in command:
        print(f"⚡ [SYS] Artoo routing Spotify API request to {target_node.upper()}: '{command}'")
        try:
            # FIX: target_node is now explicitly passed as the third argument
            output = subprocess.check_output(
                [
                    "/home/shane/google-labs/gemma_stable_env/bin/python", 
                    "/home/shane/google-labs/spotify_control.py", 
                    command, 
                    target_node
                ], 
                stderr=subprocess.STDOUT, 
                text=True
            )
            return output.strip()
            
        except subprocess.CalledProcessError as e:
            # If the Spotify script exits with an error (e.g., 404, Device Offline), 
            # this captures the exact print statement and feeds it back to Gemma's brain.
            error_msg = e.output.strip() if e.output else str(e)
            print(f"[!] Artoo Execution Failed: {error_msg}")
            return f"Error executing Spotify command: {error_msg}"

    # --- 2. HOME ASSISTANT ROUTING (Tinytuya / Kasa) ---
    # As per HOME_ASSISTANT.md policy, Artoo handles these locally without cloud APIs
    elif "light" in command or "plug" in command or "turn" in command:
        print(f"⚡ [SYS] Artoo routing Home Assistant request: '{command}'")
        # TODO: Insert your specific Kasa/Tinytuya execution scripts here.
        # Example structure:
        # output = subprocess.check_output(["python", "smart_home_control.py", command], text=True)
        # return output
        return f"Simulated Home Assistant success for command: {command}"

    # --- 3. RAW SYSTEM / LAB COMMANDS ---
    else:
        print(f"⚡ [SYS] Artoo executing raw system command: '{command}'")
        try:
            # Only execute completely safe, read-only or strictly defined lab commands here
            if command in ["uptime", "date", "whoami", "free -m", "df -h"]:
                output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT)
                return f"System Output:\n{output.strip()}"
            else:
                return f"Command '{command}' is not in the safe-list for direct shell execution."
        except subprocess.CalledProcessError as e:
            return f"Command failed: {e.output}"