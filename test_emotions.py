import sys
import os
import time
sys.path.append('/home/shane/google-labs')
from gemma_speaks import play_emotion

def test_audio_paths():
    emotions = ["ack", "chat", "acknowledged", "error", "worried", "1-screaming"]
    for e in emotions:
        path = f"/home/shane/google-labs/audio/{e}.wav"
        if not os.path.exists(path):
            print(f"[-] FAILED: {e}.wav missing")
            return False
        print(f"[+] Found: {e}.wav")
    return True

def test_trigger_latency():
    print("[*] Testing non-blocking aplay trigger...")
    start = time.time()
    # Triggering the longest file (screaming) to ensure it doesn't block
    play_emotion("confirm_long", "artoo sysadmin")
    end = time.time()
    latency = (end - start) * 1000
    print(f"[*] Trigger Latency: {latency:.2f}ms")
    return latency < 50 # Must be sub-50ms to pass

if __name__ == "__main__":
    if test_audio_paths() and test_trigger_latency():
        print("[\u2713] EMOTION ENGINE PASS")
        sys.exit(0)
    else:
        print("[X] EMOTION ENGINE FAIL")
        sys.exit(1)
