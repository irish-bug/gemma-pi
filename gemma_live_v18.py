# --- v18.0.0 Gemma Live: Root-Level Tool Intercept Protocol ---
# Change Message (v18.0.1): 
# - Update main to include circuit breaker logic and safety interlock

import asyncio, base64, json, os, sys, websockets, threading, time, subprocess
import numpy as np
import sounddevice as sd
from openwakeword.model import Model

# --- 1. CONFIG ---
API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-2.0-flash"
VOICE = "Aoede"

HW_FS, API_IN_FS, API_OUT_FS = 48000, 16000, 24000
IN_RATIO, OUT_RATIO = 3, 2
MIC_BOOST, OUT_BOOST = 8.0, 1.2 

input_queue = asyncio.Queue()
output_buffer = []
buffer_lock = threading.Lock()
is_gemma_outputting_sound = False 
last_activity_time = time.time()

oww_model = Model(wakeword_models=["hey_mycroft"], inference_framework="onnx")

# --- 2. LOCAL TOOLS ---
def local_artoo_executor(command):
    cmd_lower = command.lower()
    
    # Direct routing for local music/album playback 
    if "album" in cmd_lower or "play" in cmd_lower:
        try:
            labs_dir = os.path.expanduser("~/google-labs")
            script_path = os.path.join(labs_dir, "spotify_control.py")
            clean_cmd = command.lower().replace("tell artoo", "").strip()
            
            # Clone system environment and inject Spotify credentials explicitly
            spotify_env = os.environ.copy()
            spotify_env["SPOTIPY_CLIENT_ID"] = "9d6fbdf00c2c40abafa3949764ef2fe1"
            spotify_env["SPOTIPY_CLIENT_SECRET"] = "912d11c2ce22432ab78bcbb449bd0c9e"
            spotify_env["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8888/callback"
            
            print(f"⚡ [SYS] Artoo executing Spotify script with args: '{clean_cmd}'")
            
            # Force the script to run INSIDE the google-labs directory where .cache lives
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
            
    # Default fallback for regular lab infrastructure/system commands
    else:
        try:
            result = subprocess.check_output(["gemini", "--model", "gemini-3.1-flash-lite-preview", "--approval-mode", "yolo", command], text=True)
            return result
        except Exception as e:
            return f"Error contacting Artoo: {str(e)}"

# --- 3. AUDIO HANDLERS ---
def mic_callback(indata, frames, time, status):
    if not is_gemma_outputting_sound:
        loop.call_soon_threadsafe(input_queue.put_nowait, indata.copy())

def spk_callback(outdata, frames, time, status):
    global output_buffer, is_gemma_outputting_sound
    with buffer_lock:
        if len(output_buffer) >= frames:
            chunk = np.array(output_buffer[:frames], dtype=np.float32)
            outdata[:, 0] = np.clip(chunk * OUT_BOOST, -1.0, 1.0)
            output_buffer = output_buffer[frames:]
            is_gemma_outputting_sound = np.max(np.abs(chunk)) > 0.01
        else:
            outdata.fill(0); is_gemma_outputting_sound = False 

# --- 4. THE LIVE BRAIN ---
async def start_gemini_session():
    global last_activity_time
    last_activity_time = time.time()
# The standard BidiGenerateContent endpoint for Live WebSocket sessions
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"    
    try:
        async with websockets.connect(uri) as ws:
            setup = {
                "setup": {
                    "model": f"models/{MODEL}",
                    "generation_config": {
                        "response_modalities": ["AUDIO"],
                        "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": VOICE}}}
                    },
                    "system_instruction": {
                        "parts": [{
                            "text": "Your name is Gemma. You are a witty AI. You have a local assistant named Artoo. Whenever the user commands you to run a lab task, play music, or tells you to 'tell artoo' to do something, you MUST execute the run_artoo_cmd tool immediately. Do not just speak about doing it—fire the tool. Be concise."
                        }]
                    },
                    "tools": [{
                        "functionDeclarations": [{
                            "name": "run_artoo_cmd", 
                            "description": "Run lab commands or control Spotify music playback (e.g., 'album Abbey Road' or 'play Come Together').", 
                            "parameters": {
                                "type": "object", 
                                "properties": {
                                    "command": {"type": "string"}
                                }, 
                                "required": ["command"]
                            }
                        }]},
                        {"googleSearch": {}}
                    ]
                }
            }
            await ws.send(json.dumps(setup))
            await ws.recv() 
            print("\n[LIVE] Session Active.")

            async def send_loop():
                global last_activity_time
                while True:
                    indata = await input_queue.get()
                    downsampled = indata[::IN_RATIO]
                    audio_int16 = (np.clip(downsampled * MIC_BOOST, -1.0, 1.0) * 32767).astype(np.int16)
                    await ws.send(json.dumps({"realtime_input": {"audio": {"data": base64.b64encode(audio_int16.tobytes()).decode(), "mime_type": "audio/L16;rate=16000"}}}))
                    
                    if time.time() - last_activity_time > 60:
                        print("\n[!] Watchdog: Reverting to local wake-word...")
                        return # Exit the loop

            async def receive_loop():
                global last_activity_time
                async for message in ws:
                    msg = json.loads(message)
                    last_activity_time = time.time() # Reset on any server activity
                    
                    # NEW (v17.2.1): Capture Tool Calls as root-level WebSocket objects
                    if "toolCall" in msg:
                        function_calls = msg["toolCall"].get("functionCalls", [])
                        for fc in function_calls:
                            call_id = fc.get("id")
                            func_name = fc.get("name")
                            cmd_args = fc.get("args", {}).get("command", "")
                            
                            print(f"\n🔧 [TOOL CALL] Gemma invoked '{func_name}' with string: '{cmd_args}'")
                            
                            # Execute the pipeline locally
                            execution_result = local_artoo_executor(cmd_args)
                            
                            # Build the matching camelCase tracking payload for the Live API
                            response_payload = {
                                "tool_response": {
                                    "functionResponses": [{
                                        "id": call_id,
                                        "response": {"result": execution_result}
                                    }]
                                }
                            }
                            await ws.send(json.dumps(response_payload))
                            print(f"📡 [TOOL RESPONSE] Sent execution token back to cloud.")

                    # Handle standard streaming media channels
                    if "serverContent" in msg:
                        parts = msg["serverContent"].get("modelTurn", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                raw = base64.b64decode(part["inlineData"]["data"])
                                audio_fp32 = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
                                with buffer_lock: output_buffer.extend(np.repeat(audio_fp32, OUT_RATIO).tolist())
                            if "text" in part: 
                                print(f"\n[Gemma]: {part['text']}")

            # Run loops concurrently until termination
            done, pending = await asyncio.wait(
                [asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending: task.cancel() # Clean exit cleanup

    except Exception as e:
        print(f"\n[!] Session Closed: {e}")

async def main():
    global loop
    loop = asyncio.get_running_loop()
    
    # --- HARDWARE GATES ---
    # These contexts link the Anker S500 to our mic/spk callbacks
    with sd.InputStream(channels=1, samplerate=HW_FS, callback=mic_callback, blocksize=3840), \
         sd.OutputStream(channels=1, samplerate=HW_FS, callback=spk_callback, blocksize=1024):
        
        print("\n[*] HOLMES IV Listening... ('Hey Mycroft')")
        
        while True:
            # Wait for wake word inference data from the OWW worker
            indata = await input_queue.get()
            
            # Wake word prediction logic
            if oww_model.predict((indata[::IN_RATIO] * 32767).astype(np.int16).flatten())["hey_mycroft"] > 0.5:
                print("\n[!] Wake Word Detected!")
                
                # --- CIRCUIT BREAKER ---
                # Immediate check to prevent API hammering if we are already locked out
                if os.path.exists("/tmp/gemma_locked"):
                    print("[!] Gateway Locked: Backing off...")
                    await asyncio.sleep(60) 
                    continue
                
                # Start the BidiGenerateContent session
                await start_gemini_session()
                
                # --- SAFETY INTERLOCK ---
                # Flush the queue to prevent secondary wake-word triggers 
                # caused by residual audio packets already in the buffer.
                while not input_queue.empty():
                    try:
                        input_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                        
                print("\n[*] HOLMES IV Listening... ('Hey Mycroft')")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)