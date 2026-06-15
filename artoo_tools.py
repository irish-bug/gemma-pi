# --- v2.1.0 Artoo Execution Tools (Node-Aware Dispatcher) ---
# Change Message:
# - v2.1.0: Patched the subprocess Spotify handoff. The target_node variable is now explicitly passed as sys.argv[2] to spotify_control.py, preventing the default "local" override bug. Added subprocess.STDOUT capture so Gemma can read playback errors.
# - v2.0.0: Refactored dispatcher to support 'target_node' routing for Home Assistant (tinytuya/kasa) and Spotify.

import subprocess
import json
import re
from datetime import datetime

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
        return f"Simulated Home Assistant success for command: {command}"

    # --- 3. DEDICATED LOCAL WEIGHT LOGGING ---
    elif "weight" in command or "weigh" in command or "pound" in command or "lbs" in command:
        try:
            match = re.search(r'\d+(\.\d+)?', command)
            if match:
                weight_val = match.group()
                date_str = datetime.now().strftime("%m/%d/%Y")
                log_entry = f"{date_str}: {weight_val} lbs"
                file_path = "/home/shane/Documents/health_data/weight_tracker.txt"
                with open(file_path, "a") as f:
                    f.write(log_entry + "\n")
                print(f"⚡ [SYS] Artoo logged weight to {file_path}: {log_entry}")
                return f"Successfully logged weight: {weight_val} lbs."
            else:
                return "Artoo failed: Could not detect a valid number in the weight command."
        except Exception as e:
            return f"Error logging weight: {str(e)}"

    # --- 4. RAW SYSTEM / LAB COMMANDS ---
    else:
        print(f"⚡ [SYS] Artoo executing raw system command: '{command}'")
        try:
            # Handle service restarts
            if "restart gemma" in command:
                subprocess.run(["systemctl", "--user", "restart", "gemma.service"], check=True)
                return "Successfully restarted the Gemma service."
            # Only execute completely safe, read-only or strictly defined lab commands here
            elif command in ["uptime", "date", "whoami", "free -m", "df -h"]:
                output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT)
                return f"System Output:\n{output.strip()}"
            else:
                return f"Command '{command}' is not in the safe-list for direct shell execution."
        except subprocess.CalledProcessError as e:
            return f"Command failed: {e.output}"