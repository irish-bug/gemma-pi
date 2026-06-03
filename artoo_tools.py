#__version__ = "18.0.0"
# Executes local system commands parsed from Gemma's tool calls.
#   Version: 18.0.0
    
#   This executor acts as a bridge between the cloud LLM and the local OS, 
#   routing natural language intents into specific local hardware actions. 
#   It currently supports:
#   1. Spotify Connect media routing (via spotify_control.py)
#   2. Detached asynchronous background timers (via bash sleep)
#   3. Raw native Linux CLI execution (via the 'cli:' prefix)
#   4. Fallback inference to a local shell wrapper for generic lab tasks


import os
import sys
import subprocess

def local_artoo_executor(command):
    """
    Executes local system commands parsed from Gemma's tool calls.
    """
    cmd_lower = command.lower()
    
    # 1. Direct routing for local music/album playback & stopping
    if "album" in cmd_lower or "play" in cmd_lower or "stop music" in cmd_lower or "stop" in cmd_lower:
        try:
            labs_dir = os.path.expanduser("~/google-labs")
            script_path = os.path.join(labs_dir, "spotify_control.py")
            clean_cmd = command.lower().replace("tell artoo", "").strip()
            
            spotify_env = os.environ.copy()
            spotify_env["SPOTIPY_CLIENT_ID"] = "9d6fbdf00c2c40abafa3949764ef2fe1"
            spotify_env["SPOTIPY_CLIENT_SECRET"] = "912d11c2ce22432ab78bcbb449bd0c9e"
            spotify_env["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8888/callback"
            
            print(f"⚡ [SYS] Artoo executing Spotify script with args: '{clean_cmd}'")
            
            result = subprocess.check_output(
                [sys.executable, script_path, clean_cmd], 
                text=True, 
                stderr=subprocess.STDOUT,
                cwd=labs_dir,
                env=spotify_env
            )
            return f"Artoo successfully handled the music request. Execution Log: {result.strip()}"
        except subprocess.CalledProcessError as e:
            return f"Artoo encountered a runtime issue with Spotify: {e.output.strip()}"
        except Exception as e:
            return f"Error executing Spotify command: {str(e)}"
            
    # 2. Direct routing for local timers
    elif cmd_lower.startswith("timer"):
        try:
            parts = cmd_lower.split()
            if len(parts) > 1 and parts[1].isdigit():
                seconds = int(parts[1])
                alarm_cmd = f"sleep {seconds} && for i in {{1..3}}; do aplay -q /home/shane/google-labs/audio/overwhelmed.wav; sleep 0.5; done"
                subprocess.Popen(["bash", "-c", alarm_cmd])
                print(f"⚡ [SYS] Artoo deployed background timer for {seconds} seconds.")
                return f"Artoo successfully started a timer for {seconds} seconds."
            else:
                return "Artoo failed: Timer command missing valid seconds parameter."
        except Exception as e:
            return f"Error setting timer: {str(e)}"

    # 3. Direct routing for Native Linux CLI Commands (File appends, system checks, etc.)
    elif cmd_lower.startswith("cli:"):
        try:
            raw_cmd = command[4:].strip()
            print(f"⚡ [SYS] Artoo executing raw CLI command: '{raw_cmd}'")
            
            result = subprocess.check_output(
                raw_cmd, 
                shell=True, 
                text=True, 
                stderr=subprocess.STDOUT
            )
            return f"CLI Execution successful. Output:\n{result.strip()}"
        except subprocess.CalledProcessError as e:
            return f"CLI Execution failed (Exit code {e.returncode}). Output:\n{e.output.strip()}"
        except Exception as e:
            return f"Error executing CLI command: {str(e)}"

    # 4. Default fallback for generic LLM lab infrastructure/system commands
    else:
        try:
            cli_env = os.environ.copy()
            cli_env["NODE_NO_WARNINGS"] = "1"
            
            result = subprocess.check_output(
                ["gemini", "--model", "gemini-flash-lite-latest", "--approval-mode", "yolo", command], 
                text=True, 
                env=cli_env
            )
            return result
        except Exception as e:
            return f"Error contacting Artoo: {str(e)}"