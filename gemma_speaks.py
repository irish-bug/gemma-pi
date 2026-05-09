# gemma_speaks.py (v16.3 - Operational VAD Bridge)
# Project Gemma: Neural Bridge between Artoo (CLI) and Aoede (Voice)
# Status: Gated Logic Enabled | Hardware: Anker S500 (Card 2)

import sys
import alsaaudio
import numpy as np
import time
import subprocess
import os

# --- v16.3 CONFIGURATION ---
CHANNELS = 1          # Mono for cleaner API processing
RATE = 16000          # 16kHz is the "Goldilocks" rate for Gemini Voice-to-Text
PERIOD_SIZE = 512    # Optimized buffer for 32ms latency
FORMAT = alsaaudio.PCM_FORMAT_S16_LE
THRESHOLD = 1500       # RMS sensitivity for voice detection
PATIENCE_MAX = 15     # Frames of silence before "Turn Complete"

DEBUG_MODE = "--debug" in sys.argv

def log(msg):
    if DEBUG_MODE:
        print(f"[DEBUG v16.3] {msg}")

def play_emotion(emotion, user_text="artoo"):
    """Gated Droid Audio Logic - Targets S500 on Card 2"""
    # Only plays if Artoo/Sysadmin is addressed OR if it's a survival tone
    survival_tones = ["error", "worried", "1-screaming", "overwhelmed"]
    is_addressed = True
    
    if is_addressed or emotion in survival_tones:
        path = f"/home/shane/google-labs/audio/{emotion}.wav"
        if os.path.exists(path):
            # Non-blocking aplay to prevent engine stutter
            subprocess.Popen(["aplay", "-q", "-D", "plughw:CARD=S500,DEV=0", path])

def initialize_audio():
    try:
        # Initializing Capture on Card 2 (S500)
        inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, 
                           device='plughw:CARD=S500,DEV=0', channels=CHANNELS, 
                           rate=RATE, format=FORMAT, periodsize=PERIOD_SIZE)
        return inp
    except Exception as e:
        print(f"[CRITICAL] v16.3 Hardware Initialization Failed: {e}")
        return None

def main():
    log("VAD Bridge Initializing...")
    inp = initialize_audio()
    if not inp: return

    print("--- Project Gemma v16.3: Aoede Bridge Online ---")
    patience_counter = 0
    recording = False

    try:
        while True:
            length, data = inp.read()
            
            if length > 0:
                audio_data = np.frombuffer(data, dtype=np.int16)
                amp = np.abs(audio_data).mean()
                
                if amp > THRESHOLD:
                    if not recording:
                        log("Speech Detected. Triggering Artoo Ack...")
                        play_emotion("ack") # Droid 'I am listening'
                        recording = True
                    patience_counter = 0 # Reset silence timer
                else:
                    if recording:
                        patience_counter += 1
                        if patience_counter > PATIENCE_MAX:
                            log("Silence Detected. Triggering Handoff...")
                            play_emotion("acknowledged")
                            # --- v16.4.7 COST-OPTIMIZED BRIDGE ---
                            # Using the 3.1 Flash-Lite model as requested for low-cost execution.
                            subprocess.Popen([
                                "gemini", 
                                "--approval-mode", "yolo", 
                                "--model", "gemini-3.1-flash-lite-preview",
                                "Artoo, status check. Summarize lab stability."
                            ])                            # Replaces the broken subprocess call
                            subprocess.Popen([
                                "gemini", 
                                "--yolo", 
                                "--model", "gemini-3.1-flash-lite-preview",
                                "--prompt", "Status check. Summarize lab stability."
                            ])

                            # Cooldown to prevent audio feedback loop
                            time.sleep(5)
                            
                            recording = False
                            patience_counter = 0
            
            time.sleep(0.001) # CPU Safety Valve
            
    except KeyboardInterrupt:
        print("\n[v16.3] Bridge shutting down. Secure the Lab.")

if __name__ == "__main__":
    main()