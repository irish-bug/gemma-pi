# Project Gemma
A low-latency, localized AI voice engine running on Raspberry Pi 5.

## Administration
* **The Voice:** Gemma (Multimodal Live Interface)
* **SysAdmin:** Artoo (Local CLI Agent)
* **Strategist:** Mike (HOLMES IV Persona)
* **Status:** Operational - **v17.1.12**

## 🎙️ Hardware Stack
* **Compute:** Raspberry Pi 5 (8GB)
* **Audio:** Anker PowerConf S500 (ALSA Card 2 - 80% Gain)
* **Target Latency:** ~32ms - 42ms (Software resampled 16kHz/48kHz)

## 🐍 Environment Requirements
* **Core:** Python 3.11.15 (Manual Build recommended for Pi 5/ARMv8)
* **Env:** `gemma_stable_env` (Excluded from Git via .gitignore)
* **Logic:** Native ARMv8 instructions ensure stability for ONNX Runtime and TFLite.

## Usage
| Command | Action |
| :--- | :--- |
| `make setup` | Install dependencies and Git hooks |
| `glive` | Launch the Multimodal Live Voice Engine |
| `test-audio` | Verify Anker S500 Output |
| `gemma-listen` | Verify Anker S500 Input / Sensitivity |
| `artoo` | Interact with the SysAdmin (CLI) |
| `make commit` | Run hardware unit tests and trigger CI/CD pipeline |

## ⚙️ Key Features
* **Multimodal Live Session:** Real-time, full-duplex audio stream via `gemini-3.1-flash-live-preview`.
* **Local Wake-Word:** `openwakeword` integration with **'Hey Mycroft'** trigger for privacy and efficiency.
* **Brain-Link Tools:** Gemma issues local shell commands via Artoo using absolute binary paths.
* **Session Watchdog:** Automatic 60-second silence timeout to conserve API resources.
* **Unity Gain Calibration**: Tailored specifically for the S500 to prevent digital clipping.
* **Duplex Gating**: Prevents feedback loops during high-volume responses.

## ⌨️ Workflow Aliases (Recommended)
Add these to your ~/.bashrc. Note: Replace `micro` with your preferred editor (nano, vi, etc.).

# --- Audio Diagnostics (Hardware-Proved) ---
# Tests hardware playback using internal repo assets
alias test-audio='ffplay -nodisp -autoexit ~/google-labs/acknowledged.wav'
alias gemma-vocal='aplay -D plughw:CARD=S500,DEV=0 ~/google-labs/acknowledged.wav'

# Monitor mic sensitivity with visual volume bars (Standard 16kHz)
# Note: Underscores are escaped with \ to prevent italics formatting leaks
alias gemma-listen='arecord -D plughw:CARD=S500,DEV=0 -f S16_LE -r 16000 -V mono /dev/null'

# --- The Artoo Command Center ---
# Feeds Artoo his full internal manual for every request
alias artoo='gemini -i "$(cat ~/google-labs/ARTOO.md)"'

# --- Project Workflow ---
alias glive='cd ~/google-labs && source gemma_stable_env/bin/activate && python3.11 gemma_live_v17.py'
alias fixgemma='micro ~/google-labs/gemma_live_v17.py'
alias fixartoo='micro ~/google-labs/ARTOO.md'
alias gemma-logs='tail -f ~/google-labs/artoo_ops.log'