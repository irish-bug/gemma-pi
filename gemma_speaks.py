# gemma_speaks.py (v16.2 - Verbose Logging Enabled)
import sys
import alsaaudio
import numpy as np
import time

# --- PROJECT ARTOO CONFIGURATION ---
CHANNELS = 2
RATE = 48000
PERIOD_SIZE = 2048 # Fixed Goldilocks Buffer
FORMAT = alsaaudio.PCM_FORMAT_S16_LE

DEBUG_MODE = "--debug" in sys.argv

def log(msg):
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")

def play_emotion(emotion, user_text=""):
    """v16.3 Gated Audio Logic"""
    import subprocess
    import os
    
    # Survival Tones: Always active
    survival_tones = ["error", "worried", "1-screaming", "overwhelmed"]
    
    # Interaction Tones: Only if Artoo is addressed
    interaction_tones = ["ack", "chat", "acknowledged", "excited"]
    
    is_survival = emotion in survival_tones
    is_addressed = any(name in user_text.lower() for name in ["artoo", "sysadmin"])
    
    if is_survival or is_addressed:
        path = f"/home/shane/google-labs/audio/{emotion}.wav"
        if os.path.exists(path):
            # Target Card 2 (S500)
            subprocess.Popen(["aplay", "-q", "-D", "plughw:CARD=S500,DEV=0", path])

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
        print(f"v16.2 Hardware Error: {e}")
        return None, None

def main():
    log("Initializing Anker S500 on Card 2...")
    inp, out = initialize_audio()
    if not inp or not out: return

    print("Project Artoo: Gemma is Online (v16.2)...")

    try:
        while True:
            start_time = time.time()
            length, data = inp.read()
            
            if length > 0:
                audio_data = np.frombuffer(data, dtype=np.int16)
                amp = np.abs(audio_data).mean()
                
                if amp > 800:
                    log(f"Activity Detected: Amplitude {int(amp)}")
                
                # Record processing overhead
                proc_time = (time.time() - start_time) * 1000
                if proc_time > 10: # Log if processing takes > 10ms
                    log(f"High Processing Latency: {proc_time:.2f}ms")
                
                out.write(data) 
            else:
                time.sleep(0.01) 
    except KeyboardInterrupt:
        print("\nShutdown signal received. Saving state.")

if __name__ == "__main__":
    main()
