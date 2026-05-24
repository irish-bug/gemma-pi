# MASTER MANIFEST: PROJECT GEMMA (MARK IV)

## 1. Identity & Role Assignment
- Mike (Lead): Cloud-hosted strategic advisor. Provides architecture/code.
- Artoo (SysAdmin): Local CLI agent on Pi 5. Executes commands, manages hardware/daemons.
- Gemma (Voice): Multimodal Live API interface (gemma_live_v17.py).
- Myne Jr. (Edge Brain): Offline RAG/Inference on Pi 5 AI HAT+ Pro 2 (Llama 3.2:3B via HailoRT).
- Rozemyne/Myne (Librarian): NotebookLM library management for deep research.

## 2. Technical Serial Plate (Hardware Config)
- Compute: Raspberry Pi 5 (8GB) + AI HAT+ Pro 2 (HAILO10H).
- Audio Device: Anker PowerConf S500 (plughw:CARD=S500,DEV=0).
- Latency Target: <50ms (Verified: 42.67ms).
- Sample Rate: 48,000 Hz.

## 3. Shell Alias Mapping (Shane's Environment)
- updoot: 'sudo apt update && sudo apt upgrade -y'
- gemmaenv: 'cd ~/google-labs && source gemma_stable_env/bin/activate'
- screenoff/on: Control GPIO/sysfs backlight power.
- test-audio: Hardware check via ffplay to S500.
- gemma-vocal: Direct ALSA play of 'test.wav'.
- gemma-listen: Monitor gain via arecord.
- gemma-logs: 'tail -n 20 ~/google-labs/gemma_activity.log'
- artoo: 'gemini -i "$(cat ~/google-labs/ARTOO.md)"'
- start-gemma/debug-gemma: Orchestration of the full-duplex python loop.
- log-find: grep utility for activity logs.

## 4. Engineering Hard Rules
1. Audio Path: NEVER use volatile card indices. Always use 'plughw:CARD=S500,DEV=0'.
2. Privacy: Air-gap strictly maintained. No professional lab data allowed in logs.
3. PII Shield: No PII from 'gemma_manifest.json' in Git-tracked files.
4. Git Protocol: Run 'make test' before any 'git commit'.
5. Style: Use Linux 'snake_case' for all local logic. Isolated 'camelCase' for API transit payloads only.

## 5. Behavioral Guidelines (Workspace)
- User Context First: Establish 'people.getMe()' and timezone at startup.
- Safety: Preview all write operations (Docs/Calendar/Gmail).
- Tooling: Let the extension handle ID conversion; use MIME filters for Drive searches.