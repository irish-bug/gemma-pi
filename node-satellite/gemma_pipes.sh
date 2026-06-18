#!/bin/bash
# --- v1.1.1 Shack Audio Pipes (ALSA Shared Playback) ---
# Change Message (v1.1.1):
# - Kept arecord explicitly locked to plughw:2,0 (ReSpeaker) per user requirement.
# - Migrated aplay to the ALSA 'default' multiplexer device (dmix).
# - This allows simultaneous audio stream sharing with the Raspotify service on the USB DAC.

echo 'arecord -D plughw:2,0 -r 16000 -c 1 -f S16_LE -t raw' > /tmp/mic_pipe.sh
chmod +x /tmp/mic_pipe.sh

echo 'aplay -D default -r 24000 -c 1 -f S16_LE -t raw -B 500000' > /tmp/spk_pipe.sh
chmod +x /tmp/spk_pipe.sh

echo "[*] Starting Mic Pipe (Port 10700)..."
socat TCP-LISTEN:10700,reuseaddr,fork EXEC:/tmp/mic_pipe.sh &

echo "[*] Starting Speaker Pipe (Port 10701)..."
socat TCP-LISTEN:10701,reuseaddr,fork EXEC:/tmp/spk_pipe.sh &

echo "[*] Shack Audio Pipes Active. Waiting for Gemma host..."
wait
