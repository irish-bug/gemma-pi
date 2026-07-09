# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A monorepo for a multi-node home voice-assistant project: a wake-word-triggered
voice runtime backed by the Gemini Live API, a local command dispatcher, and an
optional local RAG cache service that sits between the dispatcher and the cloud.
It's split across three physically separate machines, each with its own
subdirectory:

- **`node-artoo/`** — the voice runtime + reasoning-agent node. Two things live
  here that share hardware but are architecturally separate: a real-time voice
  I/O process (wake word → Gemini Live API WebSocket → TTS playback) and a
  separate CLI reasoning agent with shell/tool access that the voice process
  hands off to for anything beyond simple device control.
- **`node-myne/`** — a local RAG/cache service (FastAPI + ChromaDB) that the
  reasoning agent checks before escalating a query to the cloud, and writes back
  to (`/learn`) after a cloud round-trip so the same question is a local hit
  next time. See the header comments in `node-myne/rag_service.py`,
  `rag_store.py`, and `ingest.py` for the collection design (`core` /
  `reference` / `learned_cache`) and the reasoning behind the distance
  threshold and chunking choices — those comments are the actual spec.
- **`node-satellite/`** — a mic-only audio relay node (no reasoning, no local
  model) that streams audio to/from the artoo node over TCP.

Some files not yet reorganized into a `node-*/` subdirectory still live at the
repo root (`gemma_runtime.py`, `artoo_tools.py`, `gemma_tools.py`,
`spotify_control.py`, `light_control.py`, etc.) — check `node-artoo/` first for
whichever of these you're editing, since a newer copy may already exist there
independent of the root one; `git log -- <path>` is the fastest way to tell
which is current.

## Public/private split

This repo is intentionally the "safe" half of a public/private pair. Real
device IPs, credentials, health data, and personal notes live in a private
working directory on each physical node and are **never committed** —
`.gitignore` enumerates the excluded categories (`memory/`, `policies/`
non-template files, `config/`, `devices.json`, `*.log`, credential/`.env`
files, etc.). A fresh clone of this repo will be missing all of those paths;
that's expected, not a bug. Where a script needs one of them at runtime
(`policies/INFRASTRUCTURE.md`, `config/tinytuya.json`, ...), it's supplied
locally per-node and is not part of this repo.

Where a private file needs a public counterpart for someone extending this
project, the pattern is a sanitized `*_TEMPLATE.md` with placeholder values —
see `policies/HOME_ASSISTANT_TEMPLATE.md` next to the (gitignored)
`policies/HOME_ASSISTANT.md` it mirrors.

Before adding a new file here, check whether it belongs in this list or should
be `.gitignore`d instead — anything with a real IP, device ID, credential, or
personal data does not belong in this repo.

## Commands

`make test` runs a `py_compile` syntax check on the core runtime files, then
the real `unittest` suite (`test_*.py`, stdlib `unittest`/`unittest.mock`
only — no pytest, no extra deps). There is no linter config.

```bash
make setup   # installs Python deps into a local venv and a git pre-commit hook
             # that runs `make test`
make test    # py_compile + python -m unittest discover -s . -p "test_*.py"
make run     # launches the voice runtime (gemma_runtime.py)
make commit  # test -> git add -> commit -> push
make clean   # rm -rf __pycache__ .pytest_cache
```

Run a single test file directly: `python3 -m unittest test_artoo_tools -v`.

Commits in this repo require passing tests, not just a clean syntax check —
if you're changing a module that isn't covered yet, add coverage before
committing rather than relying on `py_compile` alone.

Tests live at the repo root (`test_artoo_tools.py`, `test_gemma_tools.py`,
`test_spotify_control.py`, `test_gemma_runtime.py`) rather than under
`node-*/`, since the modules they cover are themselves still at the root (see
"Some files not yet reorganized" above). `.gitignore`'s blanket `test_*`
pattern requires a matching `!test_whatever.py` exception for each new test
file, or it silently won't be tracked — check that file when adding one.

Note that `gemma_runtime.py`, `artoo_tools.py`, and `spotify_control.py` were
each given a small extract-function refactor to make their core logic
testable without real hardware/network access (wake-word gating math pulled
out of `main()`'s nested closures; Spotify query-parsing/device-matching
pulled out of `main()`). These were behavior-preserving refactors done
specifically to enable testing, not incidental cleanup — see each file's
changelog header for what moved and why.

The `Makefile`'s `ENV_DIR` and the shebang line on most scripts hardcode an
absolute path to a specific machine's venv — update those for your own
environment rather than assuming the checked-in paths are portable.

## Architecture: voice runtime → dispatcher → RAG cache → cloud

The voice runtime (`gemma_runtime.py`) is asyncio-based: `sounddevice`
callbacks handle mic/speaker I/O, OpenWakeWord runs local wake-word detection,
and on a wake event it opens a WebSocket to the Gemini Live API
(`BidiGenerateContent`). The model must support live/voice
(`bidiGenerateContent`) — not every Gemini model in a given family does; check
`available_models.md` before changing the model string. The live session
declares tool functions the model can call; tool calls are dispatched to a
local plain-text command router (`artoo_tools.py`) rather than structured
function args, so the model is prompted to emit plain commands
(`"play album abbey road"`), not pseudo-code.

The router pattern-matches the command string to decide: direct local
execution (device control, safelisted shell commands), a subprocess call out
to a dedicated script (e.g. `spotify_control.py`), or — for anything needing
real knowledge rather than device control — a check against the local RAG
cache service (`node-myne/`) before falling back to a cloud model call. A
cloud fallback's answer is written back into the cache (`/learn`) so repeat
questions resolve locally.

If you're touching the dispatcher or the RAG service, read the module-level
comments in `node-myne/rag_service.py` and `node-myne/rag_store.py` first —
several non-obvious decisions (the cosine-distance threshold, why eviction
only touches `learned_cache`, why generation model choice was A/B tested) are
explained there and shouldn't be re-derived or silently changed.
