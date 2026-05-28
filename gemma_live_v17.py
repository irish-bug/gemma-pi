#!//home/shane/google-labs/gemma_stable_env/bin/python
# --- v17.2.4 Gemma Live: Root-Level Tool Intercept Protocol ---
# Change Message (v17.2.4): 
# - Path Fix: Corrected aplay execution path to target `audio/droid_beep.wav`.
# - Cognitive Suppression: Hardened `systemInstruction` to strictly prohibit chain-of-thought monologue leaking into the audio stream prior to tool execution.
# - Watchdog Stability: Enforced `input_queue.get_nowait()` flushing upon watchdog trigger to prevent instant wake-word loopbacks.
# - Artoo Fallback & Schema Patch: Updated local fallback to target the GA `gemini-flash-lite-latest` alias. Injected `NODE_NO_WARNINGS` to suppress MaxListeners memory leak telemetry from the tmux session. Added 'stop music' to Spotify local routing to prevent Artoo from attempting to use `update_topic` for media control.

import asyncio, base64, json, os, sys, websockets, threading, time, subprocess
import numpy as np
import sounddevice as sd
from openwakeword.model import Model

# --- 1. CONFIG ---
API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash-native-audio-latest"
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
    
    # Direct routing for local music/album playback & stopping
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
            
    # Default fallback for regular lab infrastructure/system commands
    else:
        try:
            cli_env = os.environ.copy()
            cli_env["NODE_NO_WARNINGS"] = "1" # Suppresses MaxListenersExceededWarning
            
            # Executing against the dynamic flash-lite alias verified in list_models.py
            result = subprocess.check_output(
                ["gemini", "--model", "gemini-flash-lite-latest", "--approval-mode", "yolo", command], 
                text=True, 
                env=cli_env
            )
            return result
        except Exception as e:
            return f"Error contacting Artoo: {str(e)}"

# --- 3. AUDIO HANDLERS ---
def mic_callback(indata, frames, time_info, status):
    if not is_gemma_outputting_sound:
        loop.call_soon_threadsafe(input_queue.put_nowait, indata.copy())

def spk_callback(outdata, frames, time_info, status):
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
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
    
    try:
        async with websockets.connect(uri) as ws:
            setup = {
                "setup": {
                    "model": f"models/{MODEL}",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}
                    },
                    "systemInstruction": {
                        "parts": [{
                            "text": "Your name is Gemma. You are a witty AI. You have a local assistant named Artoo. When commanded to run a lab task, control music, or 'tell artoo' to do something, you MUST execute the 'run_artoo_cmd' tool immediately. DO NOT narrate your actions, plan, or say what you are about to do. Fire the tool silently and wait for the result."
                        }]
                    },
                    "tools": [{
                        "functionDeclarations": [{
                            "name": "run_artoo_cmd", 
                            "description": "Run lab commands or control Spotify music playback (e.g., 'album Abbey Road' or 'stop music').", 
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
                    
                    payload = {
                        "realtimeInput": {
                            "mediaChunks": [{
                                "mimeType": "audio/pcm;rate=16000",
                                "data": base64.b64encode(audio_int16.tobytes()).decode()
                            }]
                        }
                    }
                    await ws.send(json.dumps(payload))
                    
                    if time.time() - last_activity_time > 60:
                        print("\n[!] Watchdog: Reverting to local wake-word...")
                        while not input_queue.empty(): input_queue.get_nowait()
                        return 

            async def receive_loop():
                global last_activity_time
                async for message in ws:
                    msg = json.loads(message)
                    last_activity_time = time.time()
                    
                    if "toolCall" in msg:
                        function_calls = msg["toolCall"].get("functionCalls", [])
                        for fc in function_calls:
                            call_id = fc.get("id")
                            func_name = fc.get("name")
                            cmd_args = fc.get("args", {}).get("command", "")
                            
                            print(f"\n🔧 [TOOL CALL] Gemma invoked '{func_name}' with string: '{cmd_args}'")
                            
                            subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)
                            execution_result = local_artoo_executor(cmd_args)
                            
                            response_payload = {
                                "toolResponse": {
                                    "functionResponses": [{
                                        "id": call_id,
                                        "name": func_name,
                                        "response": {"result": execution_result}
                                    }]
                                }
                            }
                            await ws.send(json.dumps(response_payload))
                            print(f"📡 [TOOL RESPONSE] Sent execution token back to cloud.")

                    if "serverContent" in msg:
                        parts = msg["serverContent"].get("modelTurn", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                raw = base64.b64decode(part["inlineData"]["data"])
                                audio_fp32 = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
                                with buffer_lock: output_buffer.extend(np.repeat(audio_fp32, OUT_RATIO).tolist())
                            if "text" in part: 
                                print(f"\n[Gemma]: {part['text']}")

            done, pending = await asyncio.wait(
                [asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending: task.cancel() 

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"\n[!] WebSocket Closed Unexpectedly (Code {e.code}, Reason: {e.reason})")
    except Exception as e:
        print(f"\n[!] Session Closed: {e}")

async def main():
    global loop
    loop = asyncio.get_running_loop()
    try:
        with sd.InputStream(device="default", channels=1, samplerate=HW_FS, callback=mic_callback, blocksize=3840), \
             sd.OutputStream(device="default", channels=1, samplerate=HW_FS, callback=spk_callback, blocksize=1024):
            print(f"[*] HOLMES IV Listening... ('Hey Mycroft')")
            while True:
                indata = await input_queue.get()
                prediction = oww_model.predict((indata[::IN_RATIO] * 32767).astype(np.int16).flatten())
                if prediction["hey_mycroft"] > 0.5:
                    print("\n[!] Wake Word Detected!")
                    await start_gemini_session()
                    while not input_queue.empty(): input_queue.get_nowait()
    except Exception as e: print(f"[!] Stream failure: {e}")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)