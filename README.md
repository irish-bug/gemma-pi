# Project Gemma
A low-latency, hybrid AI voice engine running on Raspberry Pi 5.

## Architecture
This project utilizes a hybrid architecture:
- **CPU (Semantic Router):** Artoo (`artoo_rag.py`) performs CPU-bound vectorization.
- **NPU (Inference Engine):** Raspberry Pi AI HAT+ 2 (Hailo-10H) runs LLM inference via the 'Myne Jr.' daemon (`hailo-ollama`).

## Administration
* **Voice Engine:** Gemma (Multimodal Live Interface)
* **SysAdmin:** Artoo (Local CLI Agent)
* **Status:** Operational (Portable Hybrid Setup)

## 🎙️ Hardware Stack
* **Compute:** Raspberry Pi 5 (8GB)
* **Accelerator:** Raspberry Pi AI HAT+ 2 (Hailo-10H, 8GB AI RAM)
* **Audio:** Anker PowerConf S500

## 🛠️ Portability & Configuration
This project is configured for portability.
* **Environment:** Python 3.11+ via `gemma_stable_env` (relative paths).
* **Configuration:** Centralized in the `/config/` directory.
* **Memory:** Managed via Markdown in `/memory/`.

## Usage
| Command | Action |
| :--- | :--- |
| `make setup` | Install dependencies and Git hooks |
| `make run` | Launch the voice engine (Gemma Live) |
| `make commit` | Run local tests, stage changes, commit, and push |
| `make commit msg="msg"` | Commit with a specific message |
| `make test` | Run structural verification |

## Workflow
1. **Semantic Routing:** User voice inputs are vectorized locally by Artoo. If context-relevant (>= 0.55 similarity), the prompt is routed to the Hailo NPU.
2. **NPU Inference:** The NPU executes Llama 3.2:3b via the Myne Jr. API (`http://127.0.0.1:8000`).
3. **Control:** Gemma controls local system functions (lights, Spotify, weight logging) via the `run_artoo_cmd` tool.

## Aliases
Add these to your `~/.bashrc` (Ensure paths are updated if moving project root):
```bash
alias gemma-logs='tail -f ~/google-labs/logs/gemma.log'
alias artoo='gemini -i "$(cat ~/google-labs/ARTOO.md)"'
```
