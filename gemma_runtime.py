#!//home/shane/google-labs/gemma_stable_env/bin/python
# --- v18.2.0 Gemma Live: Spatial Multi-Node Audio ---
# Change Message (v18.2.0):
# - Implemented explicit spatial audio routing via isolated node tracking.
# - Instantiated separate OpenWakeWord instances to prevent multi-room buffer cross-contamination.
# - Gated tool acknowledgment tones and API Text-to-Speech output to play exclusively on the triggering node.

import asyncio, base64, json, os, sys, websockets, threading, time, subprocess
import numpy as np
from wyoming.client import AsyncClient
from wyoming.audio import AudioChunk
import sounddevice as sd

# Force suppress ONNX logging before any imports
os.environ["ORT_LOG_SEVERITY_LEVEL"] = "3"
import onnxruntime as ort
from openwakeword.model import Model

# IMPORT THE NEW TOOLBOXES
from artoo_tools import local_artoo_executor
from gemma_tools import handle_end_session

# --- 1. CONFIG ---
ort.set_default_logger_severity(3)

API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
MODEL = "10"
VOICE = "Aoede"

HW_FS, API_IN_FS, API_OUT_FS = 48000, 16000, 24000
IN_RATIO, OUT_RATIO = 3, 2
MIC_BOOST, OUT_BOOST = 8.0, 1.2 

input_queue = asyncio.Queue()
local_mic_queue = asyncio.Queue()
output_buffer = []
buffer_lock = threading.Lock()

is_gemma_outputting_sound = False 
last_activity_time = time.time()
is_tool_running = False 
active_node = None # Global spatial tracker: "local" or "satellite"

# --- 2. LOCAL ANKER HANDLERS ---
def mic_callback(indata, frames, time_info, status):
    if not is_gemma_outputting_sound:
        # Constantly pipe local hardware frames to the local processor queue
        downsampled = indata[::IN_RATIO].copy()
        loop.call_soon_threadsafe(local_mic_queue.put_nowait, downsampled)

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
async def start_gemini_session(satellite_client):
    global last_activity_time
    last_activity_time = time.time()
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
    
    user_context = os.environ.get("USER_CONTEXT", "User is a human interacting via voice.")
    
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
                            "text": f"Your name is Gemma. You are a witty AI. {user_context} You have a local assistant named Artoo. When commanded to run a lab task, control music, set a timer, execute a Linux shell command, or 'tell artoo' to do something, you MUST execute the 'run_artoo_cmd' tool immediately. CRITICAL: If the user asks for a system command (like checking disk space, appending data to a text file, restarting a service), you MUST translate their intent into a raw Linux Bash command and prefix it with 'cli:' (e.g., 'cli: df -h'). Do not output markdown text headers or text explanations of your thoughts. Speak your final answer directly via the audio stream. DO NOT narrate your actions, plan, or say what you are about to do. Fire tools silently and wait for the result. CRITICAL OVERRIDE: If the user says goodbye, 'go to bed', or tells you to go to sleep, NEVER use the 'run_artoo_cmd' tool. You MUST exclusively trigger the 'end_live_session' tool."
                        }]
                    },
                    "tools": [{
                        "functionDeclarations": [
                            {
                                "name": "run_artoo_cmd", 
                                "description": "Run lab commands, control Spotify, set a timer, or execute raw Bash CLI commands. For timers, output exactly 'timer [seconds]'. For Linux shell commands, translate the user's intent into bash and output exactly 'cli: [raw bash command]'.", 
                                "parameters": {
                                    "type": "object", 
                                    "properties": {"command": {"type": "string"}}, 
                                    "required": ["command"]
                                }
                            },
                            {
                                "name": "end_live_session",
                                "description": "Call this tool immediately when the user says goodbye, go to sleep, stop listening, or indicates the conversation is over.",
                                "parameters": {"type": "object", "properties": {}}
                            }
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
                    
                    payload = {
                        "realtimeInput": {
                            "mediaChunks": [{
                                "mimeType": "audio/pcm;rate=16000",
                                "data": base64.b64encode(audio_int16.tobytes()).decode()
                            }]
                        }
                    }
                    await ws.send(json.dumps(payload))
                    
                    timeout_limit = 60 if is_tool_running else 15
                    if time.time() - last_activity_time > timeout_limit:
                        print(f"\n[!] Watchdog: Timeout reached ({timeout_limit}s). Reverting to local wake-word...")
                        while not input_queue.empty(): input_queue.get_nowait()
                        return 

            async def receive_loop():
                global last_activity_time, is_tool_running, output_buffer
                async for message in ws:
                    msg = json.loads(message)
                    last_activity_time = time.time()
                    
                    if "toolCall" in msg:
                        function_calls = msg["toolCall"].get("functionCalls", [])
                        for fc in function_calls:
                            call_id = fc.get("id")
                            func_name = fc.get("name")
                            cmd_args = fc.get("args", {}).get("command", "")
                            
                            if cmd_args:
                                print(f"\n🔧 [TOOL CALL] Gemma invoked '{func_name}' with string: '{cmd_args}'")
                            else:
                                print(f"\n🔧 [TOOL CALL] Gemma invoked '{func_name}'")
                            
                            if func_name == "end_live_session":
                                should_disconnect = await handle_end_session(input_queue)
                                if should_disconnect:
                                    return 
                            else:
                                if active_node == "local":
                                    subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)
                                    
                                print("[*] Waiting for Artoo to finish execution...")
                                is_tool_running = True
                                execution_result = await asyncio.to_thread(local_artoo_executor, cmd_args)
                                is_tool_running = False
                                last_activity_time = time.time() 
                                
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
                                
                                # SPATIAL ROUTING: Output ONLY to the active node that initiated the session
                                if active_node == "satellite":
                                    chunk = AudioChunk(rate=API_OUT_FS, width=2, channels=1, audio=raw)
                                    await satellite_client.write_event(chunk.event())
                                    
                                elif active_node == "local":
                                    audio_fp32 = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
                                    with buffer_lock: 
                                        output_buffer.extend(np.repeat(audio_fp32, OUT_RATIO).tolist())
                                
                            if "text" in part: 
                                text_out = part["text"].strip()
                                print(f"\n[Gemma]: {text_out}", flush=True) 

            done, pending = await asyncio.wait(
                [asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending: task.cancel() 

    except websockets.exceptions.ConnectionClosed as e:
        print(f"\n[!] WebSocket Closed (Code {e.code}, Reason: {e.reason})")
    except Exception as e:
        print(f"\n[!] Session Closed: {e}")

async def main():
    global loop, is_gemma_outputting_sound, active_node
    loop = asyncio.get_running_loop()
    satellite_uri = "tcp://192.168.1.213:10700"
    
    # Isolated instances maintain unique buffer trees to prevent multi-room cross-talk anomalies
    local_oww = Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx")
    satellite_oww = Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx")
    
    try:
        with sd.InputStream(device="default", channels=1, samplerate=HW_FS, callback=mic_callback, blocksize=3840), \
             sd.OutputStream(device="default", channels=1, samplerate=HW_FS, callback=spk_callback, blocksize=1024):
            
            print(f"[*] Connecting to Satellite at {satellite_uri}...")
            async with AsyncClient.from_uri(satellite_uri) as satellite_client:
                print(f"[*] Gemma Listening (Anker S500 + Satellite Node)...")
                active_node = None

                async def run_session_flow():
                    global is_gemma_outputting_sound, active_node
                    print(f"\n[!] Wake Word Locked on Node: [{active_node.upper()}]")
                    
                    is_gemma_outputting_sound = True
                    if active_node == "local":
                        subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)
                    is_gemma_outputting_sound = False
                    
                    while not input_queue.empty(): input_queue.get_nowait()
                    while not local_mic_queue.empty(): local_mic_queue.get_nowait()
                    
                    await start_gemini_session(satellite_client)
                    
                    print("[*] Cooling down...")
                    end_time = time.time() + 5
                    while time.time() < end_time:
                        while not input_queue.empty(): input_queue.get_nowait()
                        await asyncio.sleep(0.1)
                        
                    local_oww.reset()
                    satellite_oww.reset()
                    print(f"[*] Listener re-armed. Released source lock from: [{active_node}]")
                    active_node = None

                # Isolated Background Processing Loops
                async def local_listener():
                    global active_node
                    while True:
                        indata = await local_mic_queue.get()
                        if active_node == "local":
                            await input_queue.put(indata)
                        elif active_node is None:
                            prediction = local_oww.predict((indata * 32767).astype(np.int16).flatten())
                            if prediction["hey_gemma"] > 0.70:
                                active_node = "local"
                                loop.create_task(run_session_flow())

                async def satellite_listener():
                    global active_node, is_gemma_outputting_sound
                    while True:
                        event = await satellite_client.read_event()
                        if event and AudioChunk.is_type(event.type):
                            chunk = AudioChunk.from_event(event)
                            audio_fp32 = np.frombuffer(chunk.audio, dtype=np.int16).astype(np.float32) / 32767.0
                            
                            if active_node == "satellite":
                                await input_queue.put(audio_fp32.reshape(-1, 1))
                            elif active_node is None and not is_gemma_outputting_sound:
                                prediction = satellite_oww.predict((audio_fp32 * 32767).astype(np.int16).flatten())
                                if prediction["hey_gemma"] > 0.70:
                                    active_node = "satellite"
                                    loop.create_task(run_session_flow())

                asyncio.create_task(local_listener())
                asyncio.create_task(satellite_listener())

                while True:
                    await asyncio.sleep(1)
                        
    except Exception as e: print(f"[!] Stream failure: {e}")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)