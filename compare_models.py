import os
import subprocess
import numpy as np
from openwakeword.model import Model

def load_audio_ffmpeg(file_path):
    """
    Pipes raw 16-bit PCM, 16kHz mono audio into numpy using ffmpeg.
    Bypasses system-level soundfile/libsndfile dependencies entirely.
    """
    cmd = [
        'ffmpeg', '-i', file_path,
        '-f', 's16le', '-ac', '1', '-ar', '16000', '-'
    ]
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return np.frombuffer(process.stdout, dtype=np.int16)

# --- Configuration ---
clips_path = "/home/shane/google-labs/audio/hey_gemma_clips/" 
model_paths = {
    "New Custom": "./models/hey_gemma.onnx",
    "Old/Bak": "./models/hey_gemma.onnx.bak"
}

# --- Initialization ---
print("Loading models...")
# Force the use of the ONNX runtime framework
models = {
    name: Model(wakeword_models=[path], inference_framework="onnx") 
    for name, path in model_paths.items()
}

# --- Execution ---
files = sorted([f for f in os.listdir(clips_path) if f.endswith(".wav")])

print(f"Testing {len(files)} clips...")

# openWakeWord processes streaming audio in 1280-sample frames (80ms at 16kHz)
CHUNK_SIZE = 1280

for clip_name in files:
    full_path = os.path.join(clips_path, clip_name)
    audio = load_audio_ffmpeg(full_path)
    
    print(f"\n--- Testing: {clip_name} ---")
    
    for name, model in models.items():
        # Reset internal model state/buffers before each file
        model.reset()
        max_clip_score = 0.0
        
        # Step through the audio array in streaming chunk increments
        for i in range(0, len(audio), CHUNK_SIZE):
            chunk = audio[i : i + CHUNK_SIZE]
            
            # openWakeWord expects uniform chunk sizes for window calculations
            if len(chunk) < CHUNK_SIZE:
                continue
                
            prediction = model.predict(chunk)
            
            # Extract the score dictionary values
            scores = list(prediction.values())
            current_score = max(scores) if scores else 0.0
            
            # Capture the peak activation value seen anywhere in the clip
            if current_score > max_clip_score:
                max_clip_score = current_score
        
        print(f"{name:<12} max confidence: {max_clip_score:.4f}")

print("\nComparison complete.")