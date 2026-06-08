Gemma Project chat context and manifest
**Project:** Project Gemma (Multi-Node Spatial AI Voice Network and Research Assistant)
**User:** Shane McFly (Computer Scientist and Cybersecurity Researcher)
**Date/Time Context:** June 8, 2026 (Golden, Colorado)
**System Preferences:** Start responses with a TL;DR. Use bullet points for long explanations. Prioritize objectivity; do not sugar-coat.

#### **1. Hardware Topology**

* **Host Node ("Gemma"):** Raspberry Pi 5. Connected to an Anker S500 speakerphone. Handles the main Gemini 2.5 Flash Native Audio API WebSocket connection, OpenWakeWord processing, and passes local OS execution through to "artoo", a Gemini-CLI model running gemini-flash-lite-latest (see gemma_tools.py).
* **System Node ("artoo"):** (on the same) Raspberry Pi 5. gemini-cli model. Handles local OS execution via Gemini-CLI model running gemini-flash-lite-latest (see ARTOO.md and artoo_tools.py).
* **Satellite Node ("satellite-of-love" aka "slove" / Shack / Shed):** Raspberry Pi Zero 2 W with a ReSpeaker 2-Mic HAT (`card 1`, `wm8960`), housed in a custom Fender mesh case. IP: `192.168.1.213`. Port: `10700`.

#### **2. Software & Architecture State**

* **Host Runtime:** `gemma_runtime.py` (Currently on v18.2.6). Running as a user systemd service (`gemma.service`). Runtime also leverages `artoo_tools.py` and `gemma_tools.py`.
* **Satellite Daemon:** `wyoming-satellite` running via `script/run` (transitioning to `wyoming-satellite.service`).
* **Audio Routing:** Native 48kHz local hardware, 16kHz OpenWakeWord detection, 16kHz network mic transmission, 24kHz Gemini API TTS generation and network playback.
* **Spatial Awareness:** A global `active_node` tracker ensures TTS and acknowledgement tones *only* play in the room where the wake word ("Hey Gemma") was triggered.
* **Key Fixes Applied:**
* Replaced Python lists with Numpy array concatenation to bypass GIL stuttering.
* Piped `0.0` silence to the TCP queue during TTS to prevent the Gemini API from timing out.
* Implemented a 1280-sample buffer accumulation for the network stream to allow OpenWakeWord to process contiguous 80ms chunks.
* Unmuted the ReSpeaker hardware at the driver level (`amixer -c 1 sset 'Capture' 80% unmute` and `cap`).


#### **3. Immediate Status & Where We Left Off**

* The network TCP connection is flawless. The Pi 5 successfully sends audio to the shack (`aplay` at 24kHz works).
* The shack's microphone is actively recording (`arecord` at 16kHz works), but the Wyoming protocol was holding the data in "standby" because it required a formal pipeline handshake to open the stream.
* **v18.2.6** of `gemma_runtime.py` was just deployed to the Pi 5. It uses the official Wyoming Python classes (`WakeUp`, `RunPipeline`, `PipelineStage`) to execute a mathematically perfect protocol handshake.
* The satellite is currently running in `--debug` mode in the foreground to trace the exact protocol responses.