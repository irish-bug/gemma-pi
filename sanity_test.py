import os
import subprocess
import numpy as np
from openwakeword.model import Model

# Use a built-in model that definitely exists
# 'alexa' or 'hey_jarvis' are usually included by default
model = Model(wakeword_models=["alexa"]) 

# Use one of your clips
path = "/home/shane/google-labs/audio/hey_gemma_clips/hey_gemma_001.wav"

def load_audio_ffmpeg(file_path):
    cmd = ['ffmpeg', '-i', file_path, '-f', 's16le', '-ac', '1', '-ar', '16000', '-']
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return np.frombuffer(process.stdout, dtype=np.int16).astype(np.float32) / 32768.0

audio = load_audio_ffmpeg(path)
model.reset()
prediction = model.predict(audio)

print(f"Prediction dictionary: {prediction}")
print(f"Max score: {max(prediction.values())}")