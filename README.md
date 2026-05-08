# Project Gemma
A low-latency, localized AI voice engine running on Raspberry Pi 5.

## Administration
* **SysAdmin:** Artoo (Local CLI Agent)
* **Status:** Operational - v16.1

## Hardware Stack
* **Compute:** Raspberry Pi 5 (8GB)
* **Audio:** Anker PowerConf S500 (ALSA Card 2)
* **Target Latency:** ~42.6ms (2048 buffer @ 48kHz)

## ⚙️ Key Features
* **Unity Gain Calibration:** Tailored specifically for the S500 to prevent digital clipping at the hardware-software interface.
* **Duplex Gating:** Prevents the agent from entering feedback loops during high-volume responses, ensuring clean duplex streams.
* **CLI Bridge:** Speak commands directly to the **Artoo** agent for local shell execution and environment management.

## CI/CD Pipeline
Managed by Artoo to ensure hardware stability:
* **Unit Testing:** Math-based latency and VAD logic verification via `test_gemma.py`.
* **Pre-Commit Hooks:** Prevents commits if unit tests fail or latency exceeds 50ms.
* **Makefile:** Standardized operational commands for the Gemma engine.

## Usage
| Command | Action |
| :--- | :--- |
| `make setup` | Install dependencies and Git hooks |
| `make test` | Run unit tests for latency/VAD |
| `make run` | Launch the Gemma Voice Engine |
| `make commit` | Run tests, stage, commit, and push |
