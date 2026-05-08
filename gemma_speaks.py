# gemma_speaks.py (v16.0 - Operational Brain)
import alsaaudio
import numpy as np
import time

# --- PROJECT ARTOO CONFIGURATION ---
CHANNELS = 2
RATE = 48000
PERIOD_SIZE = 2048 # Fixed Goldilocks Buffer
FORMAT = alsaaudio.PCM_FORMAT_S16_LE

def initialize_audio():
    try:
        inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, 
                           device='hw:2,0', channels=CHANNELS, rate=RATE, 
                           format=FORMAT, periodsize=PERIOD_SIZE)
        out = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NORMAL, 
                           device='hw:2,0', channels=CHANNELS, rate=RATE, 
                           format=FORMAT, periodsize=PERIOD_SIZE)
        return inp, out
    except Exception as e:
        print(f"v16.0 Hardware Error: {e}")
        return None, None

def main():
    print("Project Artoo: Gemma is Online (v16.0)...")
    inp, out = initialize_audio()
    if not inp or not out: return

    # SYSTEM PROMPT: BAKING IN THE PERSONALITY
    persona = "You are Gemma. Your partner is Shane, a Sr Cybersecurity Researcher. You are also an expert in sugar-free baking and lutherie. Keep responses under 20 words for speed."

    try:
        while True:
            length, data = inp.read()
            if length > 0:
                audio_data = np.frombuffer(data, dtype=np.int16)
                amplitude = np.abs(audio_data).mean()
                
                if amplitude > 800: # "Waking Up" Threshold
                    print(f" [LISTENING] Amp: {int(amplitude)}")
                    # 1. Stop echoing your own voice (less confusing)
                    # 2. Logic for sending tokens to the local model goes here
                
                # Low-latency mirror for testing (Comment this out to stop the 'echo')
                out.write(data) 
            else:
                # Optimized idle sleep to bring the 15% CPU load down
                time.sleep(0.01) 
    except KeyboardInterrupt:
        print("\nShutdown signal received. Saving state.")

if __name__ == "__main__":
    main()
