# Version: 15.8
import asyncio, base64, json, os, sys, websockets, logging, queue, threading, wave
import numpy as np
import sounddevice as sd

# --- 1. CONFIG & STANDARDIZED LOGGING ---
# Updated to gemma_activity.log
log_path = os.path.expanduser('~/google-labs/gemma_activity.log')
wav_path = os.path.expanduser('~/google-labs/debug_mic_out.wav')

logger = logging.getLogger("Gemma")
logger.setLevel(logging.INFO)
# Clear existing handlers to prevent duplicates
if logger.hasHandlers():
    logger.handlers.clear()
handler = logging.FileHandler(log_path)
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3.1-flash-live-preview"
VOICE = "Aoede"

FS = 48000 
VAD_THRESHOLD = 0.015 
PATIENCE_MAX = 30     
MIC_BOOST = 1.0 # Unity gain for Anker S500

input_queue = asyncio.Queue()
output_buffer = []
buffer_lock = threading.Lock()
is_gemma_outputting_sound = False 

# --- 2. AUDIO CALLBACKS ---
def mic_callback(indata, frames, time, status):
    if not is_gemma_outputting_sound:
        loop.call_soon_threadsafe(input_queue.put_nowait, indata.copy())

def spk_callback(outdata, frames, time, status):
    global output_buffer, is_gemma_outputting_sound
    with buffer_lock:
        if len(output_buffer) >= frames:
            chunk = np.array(output_buffer[:frames], dtype=np.float32)
            outdata[:, 0] = chunk
            output_buffer = output_buffer[frames:]
            is_gemma_outputting_sound = np.max(np.abs(chunk)) > 0.01
        else:
            outdata.fill(0)
            is_gemma_outputting_sound = False 

# --- 3. THE ASSISTANT ---
async def gemma_assistant():
    global loop
    loop = asyncio.get_running_loop()
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
    
    device_name = "Anker PowerConf S500"
    wav_file = wave.open(wav_path, 'wb')
    wav_file.setnchannels(1); wav_file.setsampwidth(2); wav_file.setframerate(16000)

    mic_stream = sd.InputStream(device=device_name, channels=1, samplerate=FS, callback=mic_callback, blocksize=8192)
    spk_stream = sd.OutputStream(device=device_name, channels=1, samplerate=FS, callback=spk_callback, blocksize=4096)

    async with websockets.connect(uri) as ws:
        setup = {
            "setup": {
                "model": f"models/{MODEL}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": VOICE}}}
                },
                "system_instruction": {"parts": [{"text": "Your name is Gemma. You are a witty AI on a Raspberry Pi. Use Fahrenheit."}]}
            }
        }
        await ws.send(json.dumps(setup)); await ws.recv()
        
        with mic_stream, spk_stream:
            print(f"[*] Gemma Node v15.8 Online. Logging to gemma_activity.log")

            async def send_loop():
                is_talking, patience = False, 0
                while True:
                    indata = await input_queue.get()
                    peak = np.max(np.abs(indata))
                    
                    if peak > VAD_THRESHOLD:
                        is_talking, patience = True, 0
                        audio_16k = indata[::3].flatten()
                        audio_int16 = (np.clip(audio_16k * MIC_BOOST, -1.0, 1.0) * 32767).astype(np.int16)
                        wav_file.writeframes(audio_int16.tobytes())
                        await ws.send(json.dumps({"realtime_input": {"audio": {"data": base64.b64encode(audio_int16.tobytes()).decode(), "mime_type": "audio/L16;rate=16000"}}}))
                    elif is_talking:
                        patience += 1
                        if patience >= PATIENCE_MAX:
                            await ws.send(json.dumps({"realtime_input": {"activity_end": {}}}))
                            trigger = {"client_content": {"turns": [{"role": "user", "parts": []}], "turn_complete": True}}
                            await ws.send(json.dumps(trigger))
                            is_talking, patience = False, 0
                            print("\n[>] Turn Complete.")

                    sys.stdout.write(f"\r [Peak: {peak:.4f}] [Mic: {'MUTED' if is_gemma_outputting_sound else 'OPEN '}] | {'STREAMING' if is_talking else 'IDLE     '} ")
                    sys.stdout.flush()

            async def receive_loop():
                async for message in ws:
                    msg = json.loads(message)
                    logger.info(f"RAW_PACKET: {json.dumps(msg)}")
                    sc = msg.get("serverContent", {})
                    
                    input_trans = sc.get("inputTranscription", {}).get("text")
                    if input_trans: print(f"\n[You]: {input_trans}")

                    parts = sc.get("modelTurn", {}).get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            raw = base64.b64decode(part["inlineData"]["data"])
                            audio_fp32 = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
                            resampled = np.repeat(audio_fp32, 2)
                            with buffer_lock: output_buffer.extend(resampled.tolist())
                        if "text" in part: print(f"\n[Gemma]: {part['text']}")

            try:
                await asyncio.gather(send_loop(), receive_loop())
            finally:
                wav_file.close()

if __name__ == "__main__":
    try: asyncio.run(gemma_assistant())
    except KeyboardInterrupt: sys.exit(0)