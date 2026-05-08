# gemma_speaks.py (v15.9.1 - Buffer Optimization)
import alsaaudio
import numpy as np
import time

# --- PROJECT ARTOO CONFIGURATION ---
CHANNELS = 2
RATE = 48000
# Bumped to 2048 to eliminate 'scratchy' Xruns while keeping latency ~42ms
PERIOD_SIZE = 2048 
FORMAT = alsaaudio.PCM_FORMAT_S16_LE

def initialize_audio():
    try:
        # Capture: The 'Ears' (hw:2,0) - Non-blocking
        inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, 
                           device='hw:2,0', channels=CHANNELS, rate=RATE, 
                           format=FORMAT, periodsize=PERIOD_SIZE)
        
        # Playback: The 'Mouth' (hw:2,0) - Normal blocking mode for stability
        out = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NORMAL, 
                           device='hw:2,0', channels=CHANNELS, rate=RATE, 
                           format=FORMAT, periodsize=PERIOD_SIZE)
        
        print(f"v15.9.1: Buffer optimized to {PERIOD_SIZE} for smooth audio.")
        return inp, out
    except Exception as e:
        print(f"v15.9.1 Hardware Error: {e}")
        return None, None

def main():
    print("Project Artoo: Starting Smoothing Test (v15.9.1)...")
    inp, out = initialize_audio()
    if not inp or not out: return

    try:
        while True:
            # Read from microphone
            length, data = inp.read()
            if length:
                # Basic Duplex Echo to test clarity
                out.write(data) 
            else:
                # Tight sleep to keep CPU usage low while idling
                time.sleep(0.001) 
    except KeyboardInterrupt:
        print("\nStopping audio engine.")

if __name__ == "__main__":
    main()
