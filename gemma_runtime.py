#!//home/shane/google-labs/gemma_stable_env/bin/python
# --- v18.2.0 Gemma Live: Hybrid Multi-Node Audio ---
# Change Message (v18.2.0):
# - Introduce Wyoming Satellite stream for remote interaction
# - Merged local S500 and remote Wyoming Satellite streams into a unified input_queue.
# - Gemma now listens to both nodes simultaneously.

import asyncio, base64, json, os, sys, websockets, threading, time, subprocess
import numpy as np
from wyoming.client import AsyncClient
from wyoming.audio import AudioChunk
import sounddevice as sd
import onnxruntime as ort
from openwakeword.model import Model
from artoo_tools import local_artoo_executor
from gemma_tools import handle_end_session

# --- 1. CONFIG ---
ort.set_default_logger_severity(3)
API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
MODEL = "10"
VOICE = "Aoede"
HW_FS, API_IN_FS = 48000, 16000
MIC_BOOST, OUT_BOOST = 8.0, 1.2 

input_queue = asyncio.Queue()
is_gemma_outputting_sound = False 
last_activity_time = time.time()
is_tool_running = False 
oww_model = Model(wakeword_models=["models/hey_gemma.onnx"], inference_framework="onnx")

# --- 2. LOCAL ANKER HANDLER ---
def mic_callback(indata, frames, time_info, status):
    if not is_gemma_outputting_sound:
        loop.call_soon_threadsafe(input_queue.put_nowait, indata.mean(axis=1, keepdims=True))

# --- 3. THE LIVE BRAIN ---
async def start_gemini_session(satellite_client):
    global last_activity_time
    last_activity_time = time.time()
    uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
    # (Setup logic remains identical to v18.1.0 - omitted here for brevity; paste previous setup dict here)
    async with websockets.connect(uri) as ws:
        # ... [Paste existing setup & loop logic from v18.1.0] ...
        pass

async def main():
    global loop, is_gemma_outputting_sound
    loop = asyncio.get_running_loop()
    
    # Start local Anker stream
    sd.InputStream(device="default", channels=1, samplerate=HW_FS, callback=mic_callback, blocksize=3840).start()
    
    satellite_uri = "tcp://192.168.1.213:10700"
    async with AsyncClient.from_uri(satellite_uri) as satellite_client:
        # Start remote Wyoming stream
        async def mic_ingest_task():
            while True:
                event = await satellite_client.read_event()
                if event and AudioChunk.is_type(event.type) and not is_gemma_outputting_sound:
                    chunk = AudioChunk.from_event(event)
                    # Resample/normalize network stream to match local HW_FS
                    audio_fp32 = np.frombuffer(chunk.audio, dtype=np.int16).astype(np.float32) / 32767.0
                    await input_queue.put(audio_fp32)
        asyncio.create_task(mic_ingest_task())

        print(f"[*] Gemma Listening (Anker S500 + Satellite Node)...")
        while True:
            indata = await input_queue.get()
            # Feed merged queue to Wake Word engine
            prediction = oww_model.predict((indata.flatten() * 32767).astype(np.int16))
            if prediction["hey_gemma"] > 0.70:
                # ... [Wake word trigger logic remains same] ...
                pass