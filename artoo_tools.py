import os
import sys
import subprocess
import time
import re

__version__ = "18.0.8"

def local_artoo_executor(command, target_node="local"):
    """
    Executes local system commands parsed from Gemma's tool calls.
    Version: 18.0.8
    
    CHANGELOG:
    - v18.0.8: Added Spatial Node Routing (target_node parameter). Injected SSH execution for Spotify, Timers, and CLI commands when targeting the 'satellite' node in the shed.
    - v18.0.7: Injected gemma_stable_env/bin into the fallback PATH so Artoo can natively find python-installed executables like gcalcli without searching the disk.
    - v18.0.6: Removed hardcoded calendar names. Instructed Artoo to explicitly read his MEMORY.md file to resolve calendar ownership before running gcalcli.
    """
    cmd_lower = command.lower()
    
    # 1. Direct routing for local music/album playback & stopping
    if "album" in cmd_lower or "play" in cmd_lower or "stop music" in cmd_lower or "stop" in cmd_lower:
        try:
            clean_cmd = command.lower().replace("tell artoo", "").strip()
            
            if target_node == "satellite":
                print(f"⚡ [SYS] Artoo routing Spotify request to SATELLITE (Shed): '{clean_cmd}'")
                # Assumes spotify_control.py is also located at ~/google-labs on the Pi Zero
                result = subprocess.check_output(
                    ["ssh", "shane@192.168.1.213", "python3", "/home/shane/google-labs/spotify_control.py", clean_cmd],
                    text=True, 
                    stderr=subprocess.STDOUT
                )
                return f"Artoo successfully handled the music request on the satellite. Execution Log: {result.strip()}"
                
            else:
                labs_dir = os.path.expanduser("~/google-labs")
                script_path = os.path.join(labs_dir, "spotify_control.py")
                
                spotify_env = os.environ.copy()
                spotify_env["SPOTIPY_CLIENT_ID"] = "9d6fbdf00c2c40abafa3949764ef2fe1"
                spotify_env["SPOTIPY_CLIENT_SECRET"] = "912d11c2ce22432ab78bcbb449bd0c9e"
                spotify_env["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8888/callback"
                
                print(f"⚡ [SYS] Artoo executing Spotify script locally with args: '{clean_cmd}'")
                
                result = subprocess.check_output(
                    [sys.executable, script_path, clean_cmd], 
                    text=True, 
                    stderr=subprocess.STDOUT,
                    cwd=labs_dir,
                    env=spotify_env
                )
                return f"Artoo successfully handled the local music request. Execution Log: {result.strip()}"
        except subprocess.CalledProcessError as e:
            return f"Artoo encountered a runtime issue with Spotify on {target_node}: {e.output.strip()}"
        except Exception as e:
            return f"Error executing Spotify command: {str(e)}"
            
    # 2. Direct routing for local timers
    elif cmd_lower.startswith("timer"):
        try:
            parts = cmd_lower.split()
            if len(parts) > 1 and parts[1].isdigit():
                seconds = int(parts[1])
                alarm_cmd = f"sleep {seconds} && for i in {{1..3}}; do aplay -q /home/shane/google-labs/audio/overwhelmed.wav; sleep 0.5; done"
                
                if target_node == "satellite":
                    subprocess.Popen(["ssh", "shane@192.168.1.213", alarm_cmd])
                    print(f"⚡ [SYS] Artoo deployed background timer for {seconds} seconds to SATELLITE.")
                    return f"Artoo successfully started a timer for {seconds} seconds in the shed."
                else:
                    subprocess.Popen(["bash", "-c", alarm_cmd])
                    print(f"⚡ [SYS] Artoo deployed background timer for {seconds} seconds locally.")
                    return f"Artoo successfully started a timer for {seconds} seconds."
            else:
                return "Artoo failed: Timer command missing valid seconds parameter."
        except Exception as e:
            return f"Error setting timer: {str(e)}"

    # 3. Direct routing for Local Weight Logging (Always Local)
    elif "weight" in cmd_lower or "weigh" in cmd_lower or "pound" in cmd_lower or "lbs" in cmd_lower:
        try:
            match = re.search(r'\d+(\.\d+)?', cmd_lower)
            if match:
                weight_val = match.group()
                date_str = time.strftime('%m/%d/%Y')
                log_entry = f"{date_str}: {weight_val} lbs"
                
                file_path = "/home/shane/Documents/health_data/weight_tracker.txt"
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
            
            if target_node == "satellite":
                print(f"⚡ [SYS] Artoo executing raw CLI command on SATELLITE: '{raw_cmd}'")
                result = subprocess.check_output(
                    ["ssh", "shane@192.168.1.213", raw_cmd], 
                    text=True, 
                    stderr=subprocess.STDOUT
                )
            else:
                print(f"⚡ [SYS] Artoo executing raw CLI command locally: '{raw_cmd}'")
                result = subprocess.check_output(
                    raw_cmd, 
                    shell=True, 
                    text=True, 
                    stderr=subprocess.STDOUT
                )
            return f"CLI Execution successful on {target_node}. Output:\n{result.strip()}"
        except subprocess.CalledProcessError as e:
            return f"CLI Execution failed on {target_node} (Exit code {e.returncode}). Output:\n{e.output.strip()}"
        except Exception as e:
            return f"Error executing CLI command: {str(e)}"

    # 5. Default fallback for generic LLM lab infrastructure (Always Local)
    else:
        try:
            cli_env = os.environ.copy()
            cli_env["NODE_NO_WARNINGS"] = "1"
            cli_env["HOME"] = "/home/shane"
            cli_env["USER"] = "shane"
            
            venv_bin = "/home/shane/google-labs/gemma_stable_env/bin"
            existing_path = cli_env.get("PATH", "")
            cli_env["PATH"] = f"{venv_bin}:{existing_path}"
            
            current_time = time.strftime('%A, %B %d, %Y at %I:%M %p')
            
            artoo_identity = (
                f"You are Artoo, a local Linux shell assistant. "
                f"CRITICAL TEMPORAL ANCHOR: The current system date and time is {current_time}. "
                "CRITICAL MEMORY DIRECTIVE: You are strictly forbidden from writing or storing ANYTHING in ~/.gemini/tmp/ or any other temporary cache. "
                "Your core identity and system configuration live permanently in ~/google-labs/ARTOO.md. "
                "ALL dynamic knowledge, learned facts, contact mappings, and ongoing project states MUST be saved to and read from the ~/google-labs/memory/ directory. "
                "If asked to check calendars, you MUST use the 'gcalcli' command-line tool. "
                "The user has defined custom lab shortcut aliases in ~/.artoo_aliases. "
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