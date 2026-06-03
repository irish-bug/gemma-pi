#!//home/shane/google-labs/gemma_stable_env/bin/python
# --- v18.0.0 Gemma Live: Modular Architecture Refactor ---
# Change Message (v18.0.0):
# - Structural Refactor: Extracted `local_artoo_executor` into a standalone `artoo_tools.py` module to cleanly separate the websocket/audio streaming engine from OS-level tool executions. 
# - Carried over all context tweaks (186 Pinto St, 0.85 threshold, 5s cooldown, cli execution capabilities).

import asyncio, base64, json, os, sys, websockets, threading, time, subprocess
import numpy as np
import sounddevice as sd
import onnxruntime as ort
from openwakeword.model import Model

# IMPORT THE NEW TOOLBOX
from artoo_tools import local_artoo_executor

# --- 1. CONFIG ---
ort.set_default_logger_severity(3)

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

oww_model = Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx")


# --- 2. AUDIO HANDLERS ---
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

# --- 3. THE LIVE BRAIN ---
async def start_gemini_session():
    global last_activity_time
    last_activity_time = time.time()
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
    
    user_context = "User is Shane. Location is 186 Pinto St. Golden, Colorado. Timezone is MDT."
    
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
                            "text": f"Your name is Gemma. You are a witty AI. {user_context} You have a local assistant named Artoo. When commanded to run a lab task, control music, set a timer, execute a Linux shell command, or 'tell artoo' to do something, you MUST execute the 'run_artoo_cmd' tool immediately. CRITICAL: If the user asks for a system command (like checking disk space, appending data to a text file, restarting a service), you MUST translate their intent into a raw Linux Bash command and prefix it with 'cli:' (e.g., 'cli: df -h'). Do not output markdown text headers or text explanations of your thoughts. Speak your final answer directly via the audio stream. DO NOT narrate your actions, plan, or say what you are about to do. Fire tools silently and wait for the result."
                        }]
                    },
                    "tools": [{
                        "functionDeclarations": [{
                            "name": "run_artoo_cmd", 
                            "description": "Run lab commands, control Spotify, set a timer, or execute raw Bash CLI commands. For timers, output exactly 'timer [seconds]'. For Linux shell commands, translate the user's intent into bash and output exactly 'cli: [raw bash command]'.", 
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
                                text_out = part["text"].strip()
                                # Suppress printing if it looks like a Google Search chain-of-thought block
                                if not text_out.startswith("**"):
                                    print(f"\n[Gemma]: {text_out}")

            done, pending = await asyncio.wait(
                [asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending: task.cancel() 

    # Broadened to catch both normal closures (1000) and abnormal ones
    except websockets.exceptions.ConnectionClosed as e:
        print(f"\n[!] WebSocket Closed (Code {e.code}, Reason: {e.reason})")
    except Exception as e:
        print(f"\n[!] Session Closed: {e}")

async def main():
    global loop, is_gemma_outputting_sound
    loop = asyncio.get_running_loop()
    try:
        with sd.InputStream(device="default", channels=1, samplerate=HW_FS, callback=mic_callback, blocksize=3840), \
             sd.OutputStream(device="default", channels=1, samplerate=HW_FS, callback=spk_callback, blocksize=1024):
            print(f"[*] Gemma Listening... ('Hey Gemma')")
            while True:
                indata = await input_queue.get()
                prediction = oww_model.predict((indata[::IN_RATIO] * 32767).astype(np.int16).flatten())
                
                # BUMPED THRESHOLD: 0.85 prevents ghost triggers
                if prediction["hey_gemma"] > 0.85:
                    print("\n[!] Wake Word Detected!")
                    
                    # 1. Gate the mic to ignore the speaker echo
                    is_gemma_outputting_sound = True
                    
                    # 2. Play the acknowledgment tone synchronously
                    subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)
                    
                    # 3. Open the mic back up
                    is_gemma_outputting_sound = False
                    
                    # 4. Flush stale audio buffer data accumulated during the tone
                    while not input_queue.empty(): input_queue.get_nowait()
                    
                    await start_gemini_session()
                    
                    # Robust Cooldown: Flush the input queue continuously for 5 seconds to clear fan noise/echo
                    print("[*] Cooling down...")
                    end_time = time.time() + 5
                    while time.time() < end_time:
                        while not input_queue.empty():
                            input_queue.get_nowait()
                        await asyncio.sleep(0.1)
                    print("[*] Listener re-armed.")
    except Exception as e: print(f"[!] Stream failure: {e}")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)