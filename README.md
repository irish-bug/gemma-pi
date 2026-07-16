# Project Gemma

A multi-node home voice assistant: wake-word-triggered, low-latency voice I/O
over the Gemini Multimodal Live API, backed by a local reasoning agent with
shell/tool access, and a local semantic cache that exists specifically to cut
cloud token spend and latency on repeat queries. It's not a single Raspberry
Pi running one script — it's several Pis, each doing one job well, talking to
each other over TCP/link-local Ethernet.

## Architecture: three jobs, four physical nodes

| Node | Hardware | Job |
| :--- | :--- | :--- |
| **artoo** | Pi 5, physical display | Voice I/O (wake word → Gemini Live API → TTS) *and* a separate CLI reasoning agent (shell + Google Workspace access) that voice hands off to for anything beyond simple device control |
| **myne** | Pi 5 + AI HAT+ Pro 2 (Hailo-10H NPU) | Local RAG/inference only — no reasoning agent, no voice I/O, no display |
| **satellite** ("satellite-of-love", the shed) | Pi Zero 2W | Mic-only TCP audio relay — no reasoning, no local model |
| **sputnik** | Pi Zero 2W | A second, independent instance of the same mic-only audio relay role as satellite, different room |

The voice runtime and the reasoning agent live on the same physical node
(`artoo`) but are architecturally independent processes with different jobs —
don't conflate "the thing that hears you" with "the thing that decides what to
do about it." See `node-artoo/AGENTS.md` for the reasoning agent's actual
persona/protocol. Both remote audio-relay nodes run the identical
`node-satellite/` service files; `gemma_runtime.py` finds each one's real
address at runtime from the gitignored `config/nodes.json` rather than having
it hardcoded, and simply runs without a given node's listener if that node
isn't present in the local config yet.

## Agentic caching & token optimization (ongoing)

Every non-device-control query the reasoning agent can't resolve directly
(timers, lights, plugs) is meant to be checked against `node-myne`'s local
cache *before* it costs a cloud API call — that's the point of running a
dedicated NPU node instead of just calling the cloud for everything:

- `node-myne/rag_service.py` exposes `POST /query` and `POST /learn` over
  plain text (the reasoning agent never touches embeddings directly). Three
  ChromaDB collections back it: `core` (hand-curated memory/policy docs),
  `reference` (static background corpus), and `learned_cache` (a write-through
  cache of past cloud answers — a miss today becomes a local hit next time,
  via `/learn`).
- Hit/miss is decided by measured cosine distance (not a guessed similarity
  score — see `node-myne/rag_store.py` for how the threshold was derived
  against this project's actual content).
- `node-myne/evict_cache.py` runs a TTL + size-cap sweep so `learned_cache`
  doesn't grow unbounded; `core`/`reference` are hand-curated and exempt from
  eviction by design.

**Status:** wired end to end. Anything `artoo_tools.py`'s dispatcher can't
resolve as simple device control (Spotify, lights, weight logging) now checks
Myne's `POST /query` first; on a miss it escalates to the real Artoo reasoning
agent (a one-shot, non-interactive `agy --print` call — not a hardcoded
Python router pretending to be one) and writes the answer back via
`POST /learn` so the same question is a local hit next time.

## Repo layout & the public/private split

This is intentionally the *safe* half of a public/private pair. Each node
also has its own private working directory (not in this repo) holding real
device IPs, credentials, health data, and personal notes — see each
`CLAUDE.md`/`AGENTS.md` for that split's specifics. A fresh clone of this repo
is missing those paths on purpose (`memory/`, real `policies/*.md`, `config/`,
`devices.json`, etc.) — that's expected, not broken.

- **`node-artoo/`** — the voice runtime + reasoning-agent node's public slice.
- **`node-myne/`** — the local RAG/cache service.
- **`node-satellite/`** — the mic-only audio relay's service files/scripts.
- Some files (`gemma_runtime.py`, `artoo_tools.py`, `gemma_tools.py`,
  `spotify_control.py`, `light_control.py`, etc.) haven't been moved into a
  `node-*/` subdirectory yet and still live at the repo root — check
  `git log -- <path>` before assuming which copy (root vs. `node-artoo/`) is
  current.
- Where a private file needs a sanitized public counterpart, the pattern is a
  `*_TEMPLATE.md` with placeholder values (see `policies/HOME_ASSISTANT_TEMPLATE.md`).

## Hardware

- **Compute (artoo & myne):** Raspberry Pi 5 (8GB)
- **Accelerator (myne only):** Raspberry Pi AI HAT+ Pro 2 (Hailo-10H)
- **Satellite nodes (satellite-of-love, sputnik):** Raspberry Pi Zero 2W + ReSpeaker 2-Mic HAT
- **Audio (artoo):** Anker PowerConf S500

## Usage

```bash
make setup   # installs Python deps into a local venv + a git pre-commit hook
             # that runs `make test`
make test    # py_compile syntax check + the unittest suite (test_*.py)
make run     # launches the voice runtime (gemma_runtime.py)
make commit  # test -> git add -> commit -> push
make clean   # rm -rf __pycache__ .pytest_cache
```

## Testing

`make test` runs a real `unittest`/`unittest.mock`-based suite (no external
test dependencies) covering the command dispatcher, the Spotify integration's
query parsing/device matching, session-lifecycle task management, and the
wake-word gating logic (including race-condition fixes that previously had no
coverage). Tests must pass before a commit — see `CLAUDE.md` for what's
covered and what isn't yet (notably: the mic/speaker audio DSP is still
untested).
