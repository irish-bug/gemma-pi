import os
import sys
import subprocess
import time
import re

__version__ = "18.0.5"

def local_artoo_executor(command):
    """
    Executes local system commands parsed from Gemma's tool calls.
    Version: 18.0.5
    
    CHANGELOG:
    - v18.0.5: Injected dynamic Python system time into the fallback prompt to cure temporal amnesia and ensure calendar commands sync to the correct day.
    - v18.0.4: Injected `artoo_identity` prompt into the generic fallback to cure Stateless Amnesia, explicitly teaching Artoo to use `gcalcli` for calendar requests.
    
    This executor acts as a bridge between the cloud LLM and the local OS, 
    routing natural language intents into specific local hardware actions. 
    It currently supports:
    1. Spotify Connect media routing (via spotify_control.py)
    2. Detached asynchronous background timers (via bash sleep)
    3. Dedicated local weight logging (regex parsing to weight_tracker.txt)
    4. Raw native Linux CLI execution (via the 'cli:' prefix)
    5. Fallback inference to a local shell wrapper for generic lab tasks
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

    # 3. Direct routing for Local Weight Logging
    elif "weight" in cmd_lower or "weigh" in cmd_lower or "pound" in cmd_lower or "lbs" in cmd_lower:
        try:
            # Extract the first decimal or whole number from the string
            match = re.search(r'\d+(\.\d+)?', cmd_lower)
            if match:
                weight_val = match.group()
                date_str = time.strftime('%m/%d/%Y')
                log_entry = f"{date_str}: {weight_val} lbs"
                
                # Targeted to the correct health tracking document
                file_path = "/home/shane/Documents/health_data/weight_tracker.txt"
                
                # Ensure the directory exists before writing to avoid FileNotFoundError
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, "a") as f:
                    f.write(log_entry + "\n")
                    
                print(f"⚡ [SYS] Artoo logged weight to {file_path}: {log_entry}")
                return f"Artoo successfully appended '{log_entry}' to the local tracker."
            else:
                return "Artoo failed: Could not detect a valid number in the weight command."
        except Exception as e:
            return f"Error logging weight: {str(e)}"

    # 4. Direct routing for Native Linux CLI Commands
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

    # 5. Default fallback for generic LLM lab infrastructure/system commands
    else:
        try:
            cli_env = os.environ.copy()
            cli_env["NODE_NO_WARNINGS"] = "1"
            cli_env["HOME"] = "/home/shane"
            cli_env["USER"] = "shane"
            
            # THE FIX: Grab the live system time and inject it into the prompt
            current_time = time.strftime('%A, %B %d, %Y at %I:%M %p')
            
            artoo_identity = (
                f"You are Artoo, a local Linux shell assistant. "
                f"CRITICAL TEMPORAL ANCHOR: The current system date and time is {current_time}. "
                "If asked to check calendars, you MUST use the 'gcalcli' command-line tool. "
                "Emily's calendar name contains 'Emily' (use 'gcalcli agenda --calendar Emily' to check it). "
                "Do your best to execute this user request natively in the shell: "
            )
            
            enriched_command = artoo_identity + command

            result = subprocess.check_output(
                ["gemini", "--model", "gemini-flash-lite-latest", "--approval-mode", "yolo", enriched_command], 
                text=True, 
                stderr=subprocess.DEVNULL,
                env=cli_env
            )
            return result
        except Exception as e:
            return f"Error contacting Artoo: {str(e)}"