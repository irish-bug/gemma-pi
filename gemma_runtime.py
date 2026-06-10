#!//home/shane/google-labs/gemma_stable_env/bin/python
# --- v18.2.12 Gemma Live: Spatial Multi-Node Audio (24kHz Native Playback) ---
# Change Message (v18.2.12):
# - Removed 24k -> 16k Numpy downsampling for the satellite node.
# - Hardware separation on the remote node allows native 24,000 Hz playback via the USB Dongle.
# - Updated echo-cancellation duration math to calculate based on the 24kHz stream.

import asyncio, base64, json, os, sys, websockets, threading, time, subprocess
import numpy as np
import sounddevice as sd

os.environ["ORT_LOG_SEVERITY_LEVEL"] = "3"
import onnxruntime as ort
from openwakeword.model import Model

from artoo_tools import local_artoo_executor
from gemma_tools import handle_end_session

# --- 1. CONFIG ---
ort.set_default_logger_severity(3)
API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash-native-audio-latest"
VOICE = "Aoede"

HW_FS, API_IN_FS, API_OUT_FS = 48000, 16000, 24000
IN_RATIO, OUT_RATIO = 3, 2
MIC_BOOST, OUT_BOOST = 8.0, 1.2 
SATELLITE_OUT_BOOST = 0.6

input_queue = asyncio.Queue()
local_mic_queue = asyncio.Queue()
output_buffer = np.array([], dtype=np.float32) 
buffer_lock = threading.Lock()

is_gemma_outputting_sound = False 
satellite_tts_end_time = 0.0
last_activity_time = time.time()
is_tool_running = False 
active_node = None 

# --- 2. LOCAL ANKER HANDLERS ---
def mic_callback(indata, frames, time_info, status):
    downsampled = indata[::IN_RATIO].copy()
    if is_gemma_outputting_sound: downsampled.fill(0.0) 
    loop.call_soon_threadsafe(local_mic_queue.put_nowait, downsampled)

def spk_callback(outdata, frames, time_info, status):
    global output_buffer, is_gemma_outputting_sound
    with buffer_lock:
        if len(output_buffer) > 0:
            take = min(len(output_buffer), frames)
            outdata[:take, 0] = np.clip(output_buffer[:take] * OUT_BOOST, -1.0, 1.0)
            if take < frames: outdata[take:, 0] = 0 
            output_buffer = output_buffer[take:]
            is_gemma_outputting_sound = True
        else:
            outdata.fill(0)
            is_gemma_outputting_sound = False 

# --- 3. THE LIVE BRAIN ---
async def start_gemini_session(spk_writer):
    global last_activity_time, satellite_tts_end_time
    last_activity_time = time.time()
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
    user_context = os.environ.get("USER_CONTEXT", "User is a human interacting via voice.")
    
    try:
        async with websockets.connect(uri) as ws:
            setup = {
                "setup": {
                    "model": f"models/{MODEL}",
                    "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}},
                    "systemInstruction": {"parts": [{"text": f"Your name is Gemma. You are a witty AI. {user_context} You have a local assistant named Artoo. When commanded to run a lab task, control music, set a timer, execute a Linux shell command, or 'tell artoo' to do something, you MUST execute the 'run_artoo_cmd' tool immediately. CRITICAL: If the user asks for a system command (like checking disk space, appending data to a text file, restarting a service), you MUST translate their intent into a raw Linux Bash command and prefix it with 'cli:' (e.g., 'cli: df -h'). Do not output markdown text headers or text explanations of your thoughts. Speak your final answer directly via the audio stream. DO NOT narrate your actions, plan, or say what you are about to do. Fire tools silently and wait for the result. CRITICAL OVERRIDE: If the user says goodbye, 'go to bed', or tells you to go to sleep, NEVER use the 'run_artoo_cmd' tool. You MUST exclusively trigger the 'end_live_session' tool."}]},
                    "tools": [
                        {"functionDeclarations": [
                            {"name": "run_artoo_cmd", "description": "Run lab commands, control Spotify, set a timer, or execute raw Bash CLI commands.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
                            {"name": "end_live_session", "description": "Call immediately when user says goodbye.", "parameters": {"type": "object", "properties": {}}}
                        ]},
                        {"googleSearch": {}}
                    ]
                }
            }
            await ws.send(json.dumps(setup))
            await ws.recv() 
            print(f"\n[LIVE] Session Active on Node: [{active_node.upper()}]")

            async def send_loop():
                global last_activity_time, is_tool_running
                while True:
                    indata = await input_queue.get()
                    audio_int16 = (np.clip(indata * MIC_BOOST, -1.0, 1.0) * 32767).astype(np.int16)
                    payload = {"realtimeInput": {"mediaChunks": [{"mimeType": "audio/pcm;rate=16000", "data": base64.b64encode(audio_int16.tobytes()).decode()}]}}
                    await ws.send(json.dumps(payload))
                    if is_gemma_outputting_sound: last_activity_time = time.time()
                    timeout_limit = 60 if is_tool_running else 30
                    if time.time() - last_activity_time > timeout_limit:
                        print(f"\n[!] Watchdog: Timeout reached ({timeout_limit}s). Reverting to local wake-word...")
                        while not input_queue.empty(): input_queue.get_nowait()
                        return 

            async def receive_loop():
                global last_activity_time, is_tool_running, output_buffer, satellite_tts_end_time
                async for message in ws:
                    msg = json.loads(message)
                    last_activity_time = time.time()
                    
                    if "toolCall" in msg:
                        function_calls = msg["toolCall"].get("functionCalls", [])
                        for fc in function_calls:
                            call_id, func_name, cmd_args = fc.get("id"), fc.get("name"), fc.get("args", {}).get("command", "")
                            if func_name == "end_live_session":
                                if await handle_end_session(input_queue): return 
                            else:
                                if active_node == "local": subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)
                                print("[*] Waiting for Artoo to finish execution...")
                                is_tool_running = True
                                execution_result = await asyncio.to_thread(local_artoo_executor, cmd_args)
                                is_tool_running, last_activity_time = False, time.time() 
                                await ws.send(json.dumps({"toolResponse": {"functionResponses": [{"id": call_id, "name": func_name, "response": {"result": execution_result}}]}}))

                    if "serverContent" in msg:
                        for part in msg["serverContent"].get("modelTurn", {}).get("parts", []):
                            if "inlineData" in part:
                                raw = base64.b64decode(part["inlineData"]["data"])
                                if active_node == "satellite":
                                    # Streaming native 24kHz audio without downsampling!
                                    audio_16 = np.frombuffer(raw, dtype=np.int16)
                                    chunk_to_send = (audio_16 * SATELLITE_OUT_BOOST).astype(np.int16)
                                    spk_writer.write(chunk_to_send.tobytes())
                                    await spk_writer.drain()
                                    
                                    # Mathematically lock the microphone based on 24000 Hz duration
                                    duration = len(chunk_to_send) / 24000.0
                                    current = time.time()
                                    if satellite_tts_end_time < current:
                                        satellite_tts_end_time = current + duration + 0.3 
                                    else:
                                        satellite_tts_end_time += duration
                                        
                                elif active_node == "local":
                                    audio_up = np.repeat(np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0, OUT_RATIO)
                                    with buffer_lock: output_buffer = np.concatenate((output_buffer, audio_up))
                            if "text" in part: 
                                print(f"\n[Gemma's Thoughts]: {part['text'].strip()}", flush=True) 

            done, pending = await asyncio.wait([asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())], return_when=asyncio.FIRST_COMPLETED)
            for task in pending: task.cancel() 

    except websockets.exceptions.ConnectionClosed as e: print(f"\n[!] WebSocket Closed (Code {e.code})")
    except Exception as e: print(f"\n[!] Session Closed: {e}")

async def main():
    global loop, is_gemma_outputting_sound, active_node, satellite_tts_end_time
    loop = asyncio.get_running_loop()
    
    local_oww = Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx")
    satellite_oww = Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx")
    
    try:
        print("[*] Booting hardware streams (Anker S500)...")
        with sd.InputStream(device="default", channels=1, samplerate=HW_FS, callback=mic_callback, blocksize=3840), \
             sd.OutputStream(device="default", channels=1, samplerate=HW_FS, callback=spk_callback, blocksize=1024):
            
            try:
                print("[*] Connecting to Shack Mic (Port 10700)...")
                mic_reader, mic_writer = await asyncio.open_connection('192.168.1.213', 10700)
                print("[*] Connecting to Shack Speaker (Port 10701)...")
                spk_reader, spk_writer = await asyncio.open_connection('192.168.1.213', 10701)
            except Exception as e:
                print(f"[!] Failed to connect to Shack TCP pipes: {e}")
                return
                
            print(f"[*] Gemma Listening (Anker S500 + Shack TCP Pipes)...")
            active_node = None

            async def run_session_flow():
                global is_gemma_outputting_sound, active_node, satellite_tts_end_time
                print(f"\n[!] Wake Word Locked on Node: [{active_node.upper()}]")
                is_gemma_outputting_sound = True
                if active_node == "local": 
                    subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)
                elif active_node == "satellite":
                    # Removed the downsampling mask here too, assuming chat.wav is 24kHz natively.
                    chat_wav = np.fromfile("/home/shane/google-labs/audio/chat.wav", dtype=np.int16)[22:]
                    chunk_to_send = (chat_wav * SATELLITE_OUT_BOOST).astype(np.int16)
                    spk_writer.write(chunk_to_send.tobytes())
                    await spk_writer.drain()
                    satellite_tts_end_time = time.time() + (len(chunk_to_send) / 24000.0) + 0.3
                    
                is_gemma_outputting_sound = False
                
                while not input_queue.empty(): input_queue.get_nowait()
                while not local_mic_queue.empty(): local_mic_queue.get_nowait()
                await start_gemini_session(spk_writer)
                
                print("[*] Cooling down...")
                end_time = time.time() + 5
                while time.time() < end_time:
                    while not input_queue.empty(): input_queue.get_nowait()
                    await asyncio.sleep(0.1)
                    
                local_oww.reset()
                satellite_oww.reset()
                print(f"[*] Listener re-armed. Released source lock from: [{active_node}]")
                active_node = None

            async def local_listener():
                global active_node
                try:
                    while True:
                        indata = await local_mic_queue.get()
                        if active_node == "local":
                            await input_queue.put(indata)
                        elif active_node is None and not is_gemma_outputting_sound:
                            if local_oww.predict((indata * 32767).astype(np.int16).flatten())["hey_gemma"] > 0.70:
                                active_node = "local"
                                loop.create_task(run_session_flow())
                except Exception as e: print(f"\n[!] LOCAL THREAD CRASH: {e}")

            async def satellite_listener():
                global active_node, is_gemma_outputting_sound, satellite_tts_end_time
                satellite_buffer = np.array([], dtype=np.int16)
                chunk_count = 0
                try:
                    while True:
                        raw_bytes = await mic_reader.read(4096)
                        if not raw_bytes:
                            print("[!] Shack Mic Stream Closed.")
                            break
                            
                        chunk_count += 1
                        if len(raw_bytes) % 2 != 0: raw_bytes = raw_bytes[:-1]
                        audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                        
                        if chunk_count == 1:
                            print(f"[*] 📡 Shack TCP Pipe Open: First chunk received ({len(raw_bytes)} bytes)")
                        
                        mute_satellite = time.time() < satellite_tts_end_time
                        
                        if active_node == "satellite":
                            audio_fp32 = audio_int16.astype(np.float32) / 32767.0
                            if mute_satellite: audio_fp32.fill(0.0)
                            await input_queue.put(audio_fp32.reshape(-1, 1))
                        elif active_node is None and not mute_satellite:
                            satellite_buffer = np.concatenate((satellite_buffer, audio_int16))
                            while len(satellite_buffer) >= 1280:
                                frame, satellite_buffer = satellite_buffer[:1280], satellite_buffer[1280:]
                                if satellite_oww.predict(frame)["hey_gemma"] > 0.70:
                                    active_node = "satellite"
                                    loop.create_task(run_session_flow())
                                    satellite_buffer = np.array([], dtype=np.int16)
                                    break
                except Exception as e: print(f"\n[!] SATELLITE THREAD CRASH: {e}")

            asyncio.create_task(local_listener())
            asyncio.create_task(satellite_listener())
            while True: await asyncio.sleep(1)
                    
    except Exception as e: print(f"[!] Stream failure: {e}")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)