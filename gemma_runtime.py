#!/home/shane/google-labs/gemma_stable_env/bin/python
# --- v18.3.0 Gemma Live: Spatial Multi-Node Audio (Node-Aware Tools) ---
# CHANGELOG:
# - v18.3.0: Added the "sputnik" remote node (same TCP mic/speaker relay
#   protocol as satellite, 192.168.1.222:10700/10701, hey_gemma wake word --
#   see gemma-pipes.service on that node). Since there can now be more than
#   one simultaneously-connected remote node, satellite_listener() and the
#   satellite_connected/spk_writer/satellite_tts_end_time globals it used
#   (which only ever supported a single remote connection) were replaced
#   with a generalized remote_listener(node_name, host, mic_port, spk_port,
#   oww_model) plus a per-node remote_state dict, so a second node's
#   connect/disconnect can't clobber another's speaker writer or TTS mute
#   window. Node connection info (real IPs) now loads from the gitignored
#   config/nodes.json via load_remote_audio_nodes() instead of being
#   hardcoded, per CLAUDE.md's public/private split -- a checkout with no
#   private config supplied yet just runs with no remote listeners rather
#   than failing.
#
# - v18.2.19: Extracted the v18.2.18 race guard and the OWW threshold check
#   into top-level pure functions (is_listener_locked_out, wake_word_detected)
#   so they're unit-testable without booting real audio/websocket hardware.
#   No behavior change — see test_gemma_runtime.py.
#
# - v18.2.18: Fixed double-session race condition in local_listener() and
#   satellite_listener(). session_active_event.set() happens inside
#   run_session_flow(), which is launched as a background task — there is a
#   window between active_node being set synchronously and the event actually
#   being set, during which a second wake-word trigger could fire and spin up
#   a concurrent session. Fix: added `if active_node is not None: continue`
#   guard before the OWW predict call in both listeners. active_node is set
#   synchronously before create_bg_task returns, so this closes the race
#   without needing to change the session_active_event mechanism.
#   Symptom: double `[!] Wake Word Locked on Node: [LOCAL]` log entries,
#   Gemma double-responding and apparently interrupting herself.
#
# - v18.2.17: Extracted Garbage Collection (GC) task manager to gemma_tools.py
#   to improve code modularity.

import asyncio, base64, json, os, sys, websockets, threading, time, subprocess
import numpy as np
import sounddevice as sd

os.environ["ORT_LOG_SEVERITY_LEVEL"] = "4"
import onnxruntime as ort
from openwakeword.model import Model

from artoo_tools import local_artoo_executor
from gemma_tools import handle_end_session, create_bg_task

# --- 1. CONFIG ---
ort.set_default_logger_severity(4)
API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash-native-audio-latest"
VOICE = "Aoede"

HW_FS, API_IN_FS, API_OUT_FS = 48000, 16000, 24000
IN_RATIO, OUT_RATIO = 3, 2
MIC_BOOST, OUT_BOOST = 8.0, 1.2
SATELLITE_OUT_BOOST = 0.6
WAKE_WORD_THRESHOLD = 0.70

# Real node IPs/ports are infra data, not code -- they live in the gitignored
# config/nodes.json (see CLAUDE.md's public/private split), not hardcoded
# here. Only these two keys are TCP mic/speaker audio relays gemma_runtime
# listens on; other keys in the same file (e.g. "myne") are service
# endpoints other modules use, not audio nodes.
NODE_CONFIG_PATH = "/home/shane/google-labs/config/nodes.json"
AUDIO_RELAY_NODE_KEYS = ("satellite", "sputnik")


def load_remote_audio_nodes() -> dict:
    """Returns {node_name: {"host", "mic_port", "spk_port"}} for whichever
    audio-relay nodes are present in the local node config. Missing/absent
    config (e.g. a fresh checkout with no private config supplied yet) means
    no remote listeners start -- local wake-word still works on its own."""
    try:
        with open(NODE_CONFIG_PATH) as f:
            node_config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {name: node_config[name] for name in AUDIO_RELAY_NODE_KEYS if name in node_config}


def is_listener_locked_out(active_node) -> bool:
    """
    True when a wake-word listener must not run detection on the current frame:
    a session is already active, or another listener has already claimed
    active_node but hasn't set session_active_event yet.

    Checking active_node directly (not just session_active_event.is_set()) closes
    a race window (v18.2.18): active_node is set synchronously by whichever
    listener wins the wake-word race, but session_active_event is only set later,
    inside the background task that listener kicks off. Between those two
    moments, a second listener's wake-word check could otherwise still fire and
    spin up a concurrent session (symptom: double "Wake Word Locked" log lines,
    Gemma interrupting herself).
    """
    return active_node is not None


def wake_word_detected(prediction_score: float, threshold: float = WAKE_WORD_THRESHOLD) -> bool:
    """True if a single OpenWakeWord prediction score counts as a trigger."""
    return prediction_score > threshold


input_queue = asyncio.Queue()
local_mic_queue = asyncio.Queue()
output_buffer = np.array([], dtype=np.float32)
buffer_lock = threading.Lock()

is_gemma_outputting_sound = False
last_activity_time = time.time()
is_tool_running = False
active_node = None

# Event flag to cleanly pause wake-word listeners
session_active_event = asyncio.Event()

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
async def start_gemini_session(current_node, remote_state):
    """remote_state is {"connected", "spk_writer", "tts_end_time"} per remote
    audio-relay node (satellite, sputnik, ...), keyed by node name -- passed
    in explicitly rather than read off globals so a second/third remote node
    doesn't clobber another's connection state."""
    global last_activity_time
    last_activity_time = time.time()
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
    user_context = os.environ.get("USER_CONTEXT", "User is a human interacting via voice.")

    try:
        async with websockets.connect(uri) as ws:
            setup = {
                "setup": {
                    "model": f"models/{MODEL}",
                    "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}},
                    "systemInstruction": {"parts": [{"text": f"Your name is Gemma. You are a witty AI. {user_context} You have a local assistant named Artoo. CRITICAL: The user is currently talking to you through the '{current_node}' hardware node. When commanded to run a lab task, control music, set a timer, or execute a Linux shell command, you MUST execute the 'run_artoo_cmd' tool immediately. If the user asks for music or media, set the 'target_node' parameter to '{current_node}' unless they explicitly specify otherwise. Do not output markdown text headers or text explanations of your thoughts. Speak your final answer directly via the audio stream. DO NOT narrate your actions, plan, or say what you are about to do. Fire tools silently and wait for the result. CRITICAL OVERRIDE: If the user says goodbye, 'go to bed', or tells you to go to sleep, NEVER use the 'run_artoo_cmd' tool. You MUST exclusively trigger the 'end_live_session' tool."}]},
                    "tools": [
                        {"functionDeclarations": [
                            {
                                "name": "run_artoo_cmd",
                                "description": "Run lab commands, control music, set a timer, or execute raw Bash CLI commands. CRITICAL: For music, the command MUST be plain text (e.g., 'play album abbey road', 'play track let it be', 'stop'). NEVER use python syntax or fake functions like play_music().",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "command": {"type": "string", "description": "The plain text command to execute."},
                                        "target_node": {"type": "string", "description": "The execution node ('local', 'satellite', or 'chores')."}
                                    },
                                    "required": ["command", "target_node"]
                                }
                            },
                            {"name": "end_live_session", "description": "Call immediately when user says goodbye.", "parameters": {"type": "object", "properties": {}}}
                        ]},
                        {"googleSearch": {}}
                    ]
                }
            }
            await ws.send(json.dumps(setup))
            await ws.recv()
            print(f"\n[LIVE] Session Active on Node: [{current_node.upper()}]")

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
                global last_activity_time, is_tool_running, output_buffer
                async for message in ws:
                    msg = json.loads(message)
                    last_activity_time = time.time()

                    if "toolCall" in msg:
                        function_calls = msg["toolCall"].get("functionCalls", [])
                        for fc in function_calls:
                            call_id, func_name, args = fc.get("id"), fc.get("name"), fc.get("args", {})

                            if func_name == "end_live_session":
                                if await handle_end_session(input_queue): return
                            elif func_name == "run_artoo_cmd":
                                cmd_args = args.get("command", "")
                                target_node = args.get("target_node", current_node)

                                if current_node == "local":
                                    subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)

                                print(f"[*] Waiting for Artoo to execute on [{target_node.upper()}]...")
                                is_tool_running = True

                                execution_result = await asyncio.to_thread(local_artoo_executor, cmd_args, target_node)

                                is_tool_running, last_activity_time = False, time.time()
                                await ws.send(json.dumps({"toolResponse": {"functionResponses": [{"id": call_id, "name": func_name, "response": {"result": execution_result}}]}}))

                    if "serverContent" in msg:
                        for part in msg["serverContent"].get("modelTurn", {}).get("parts", []):
                            if "inlineData" in part:
                                raw = base64.b64decode(part["inlineData"]["data"])
                                if current_node == "local":
                                    audio_up = np.repeat(np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0, OUT_RATIO)
                                    with buffer_lock: output_buffer = np.concatenate((output_buffer, audio_up))

                                elif current_node in remote_state:
                                    state = remote_state[current_node]
                                    if state["connected"] and state["spk_writer"]:
                                        try:
                                            audio_16 = np.frombuffer(raw, dtype=np.int16)
                                            chunk_to_send = (audio_16 * SATELLITE_OUT_BOOST).astype(np.int16)
                                            state["spk_writer"].write(chunk_to_send.tobytes())
                                            await state["spk_writer"].drain()

                                            duration = len(chunk_to_send) / 24000.0
                                            current = time.time()
                                            if state["tts_end_time"] < current:
                                                state["tts_end_time"] = current + duration + 0.3
                                            else:
                                                state["tts_end_time"] += duration
                                        except Exception as e:
                                            print(f"\n[!] Dropped chunk. {current_node} pipe disconnected: {e}")
                                            state["connected"] = False
                            if "text" in part:
                                print(f"\n[Gemma's Thoughts]: {part['text'].strip()}", flush=True)

            done, pending = await asyncio.wait([asyncio.create_task(send_loop()), asyncio.create_task(receive_loop())], return_when=asyncio.FIRST_COMPLETED)
            for task in pending: task.cancel()

    except websockets.exceptions.ConnectionClosed as e: print(f"\n[!] WebSocket Closed (Code {e.code})")
    except Exception as e: print(f"\n[!] Session Closed: {e}")

async def main():
    global loop, is_gemma_outputting_sound, active_node
    loop = asyncio.get_running_loop()

    local_oww = Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx")

    # Every remote audio-relay node (satellite, sputnik, ...) gets its own
    # OWW instance (v18.2.0: shared instances caused multi-room buffer
    # cross-contamination) and its own connection-state dict, keyed by node
    # name, so a second node's connect/disconnect can't clobber another's
    # spk_writer/tts_end_time. Only nodes actually present in
    # config/nodes.json get a listener -- a fresh checkout with no private
    # config yet still runs fine on local wake-word alone.
    remote_audio_nodes = load_remote_audio_nodes()
    remote_oww = {name: Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx") for name in remote_audio_nodes}
    remote_state = {name: {"connected": False, "spk_writer": None, "tts_end_time": 0.0} for name in remote_audio_nodes}

    try:
        print("[*] Booting local hardware streams (Anker S500)...")
        with sd.InputStream(device="default", channels=1, samplerate=HW_FS, callback=mic_callback, blocksize=3840), \
             sd.OutputStream(device="default", channels=1, samplerate=HW_FS, callback=spk_callback, blocksize=1024):

            print(f"[*] Gemma Local Listening Active. Remote node recovery loops starting in background for: {list(remote_audio_nodes) or 'none configured'}...")
            active_node = None

            async def run_session_flow():
                global is_gemma_outputting_sound, active_node

                # Flag the system as 'busy' so listeners pause
                session_active_event.set()
                print(f"\n[!] Wake Word Locked on Node: [{active_node.upper()}]")

                is_gemma_outputting_sound = True
                if active_node == "local":
                    subprocess.run(["aplay", "-q", "/home/shane/google-labs/audio/ack.wav"], check=False)
                elif active_node in remote_state:
                    state = remote_state[active_node]
                    if state["connected"] and state["spk_writer"]:
                        try:
                            chat_wav = np.fromfile("/home/shane/google-labs/audio/chat.wav", dtype=np.int16)[22:]
                            chunk_to_send = (chat_wav * SATELLITE_OUT_BOOST).astype(np.int16)
                            state["spk_writer"].write(chunk_to_send.tobytes())
                            await state["spk_writer"].drain()
                            state["tts_end_time"] = time.time() + (len(chunk_to_send) / 24000.0) + 0.3
                        except Exception as e:
                            print(f"\n[!] Failed to play ack tone on {active_node}. Disconnected: {e}")
                            state["connected"] = False

                is_gemma_outputting_sound = False

                while not input_queue.empty(): input_queue.get_nowait()
                while not local_mic_queue.empty(): local_mic_queue.get_nowait()

                await start_gemini_session(active_node, remote_state)

                print("[*] Cooling down...")
                await asyncio.sleep(5)

                while not input_queue.empty(): input_queue.get_nowait()

                local_oww.reset()
                for oww in remote_oww.values(): oww.reset()
                print(f"[*] Listener re-armed. Released source lock from: [{active_node}]")
                active_node = None

                # Unpause the listeners
                session_active_event.clear()

            async def local_listener():
                global active_node
                try:
                    while True:
                        indata = await local_mic_queue.get()
                        if session_active_event.is_set():
                            if active_node == "local":
                                await input_queue.put(indata)
                            continue

                        if is_listener_locked_out(active_node):
                            continue

                        if not is_gemma_outputting_sound:
                            score = local_oww.predict((indata * 32767).astype(np.int16).flatten())["hey_gemma"]
                            if wake_word_detected(score):
                                active_node = "local"
                                create_bg_task(loop, run_session_flow())
                except Exception as e: print(f"\n[!] LOCAL THREAD CRASH: {e}")

            async def remote_listener(node_name, host, mic_port, spk_port, oww_model):
                global active_node
                state = remote_state[node_name]
                while True:
                    if not state["connected"]:
                        try:
                            mic_reader, mic_writer = await asyncio.open_connection(host, mic_port)
                            spk_reader, spk_writer = await asyncio.open_connection(host, spk_port)
                            state["connected"] = True
                            state["spk_writer"] = spk_writer
                            print(f"\n[*] 📡 {node_name.capitalize()} TCP Pipes Connected Successfully!")
                        except Exception:
                            await asyncio.sleep(5)
                            continue

                    node_buffer = np.array([], dtype=np.int16)
                    try:
                        while state["connected"]:
                            raw_bytes = await mic_reader.read(4096)
                            if not raw_bytes:
                                print(f"\n[!] {node_name.capitalize()} Mic Stream Closed. Entering auto-recovery...")
                                state["connected"] = False
                                break

                            if len(raw_bytes) % 2 != 0: raw_bytes = raw_bytes[:-1]
                            audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)

                            mute_node = time.time() < state["tts_end_time"]

                            if session_active_event.is_set():
                                if active_node == node_name:
                                    audio_fp32 = audio_int16.astype(np.float32) / 32767.0
                                    if mute_node: audio_fp32.fill(0.0)
                                    await input_queue.put(audio_fp32.reshape(-1, 1))
                                continue

                            if is_listener_locked_out(active_node):
                                continue

                            if not mute_node:
                                node_buffer = np.concatenate((node_buffer, audio_int16))
                                while len(node_buffer) >= 1280:
                                    frame, node_buffer = node_buffer[:1280], node_buffer[1280:]
                                    if wake_word_detected(oww_model.predict(frame)["hey_gemma"]):
                                        active_node = node_name
                                        create_bg_task(loop, run_session_flow())
                                        node_buffer = np.array([], dtype=np.int16)
                                        break
                    except Exception as e:
                        print(f"\n[!] {node_name.capitalize()} Connection Lost ({e}). Entering auto-recovery...")
                        state["connected"] = False
                        if state["spk_writer"]:
                            try: state["spk_writer"].close()
                            except: pass

            create_bg_task(loop, local_listener())
            for name, cfg in remote_audio_nodes.items():
                create_bg_task(loop, remote_listener(name, cfg["host"], cfg["mic_port"], cfg["spk_port"], remote_oww[name]))

            while True: await asyncio.sleep(1)

    except Exception as e: print(f"[!] Critical Stream failure: {e}")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)
