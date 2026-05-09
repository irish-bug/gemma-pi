import os
import subprocess

def speak_aoede(text):
    print(f"Aoede is saying: {text}")
    # This uses a simple system call to aplay for now, 
    # assuming we've pre-rendered or are using a CLI TTS tool.
    # For now, let's just trigger Artoo's 'excited' sound to confirm path.
    subprocess.Popen(["aplay", "-D", "plughw:CARD=S500,DEV=0", "/home/shane/google-labs/audio/excited.wav"])

speak_aoede("v16.3 Voice Engine Test")
