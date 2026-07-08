# Project Gemma — artoo node (voice runtime + reasoning agent)

> Placement note: this file was drafted by Claude Code from the myne side
> (google-labs) while artoo's own private working directory doesn't yet
> exist / wasn't reachable from this session. Myne's equivalent file lives
> *outside* the public monorepo, in its private working dir (`google-labs`),
> not inside `gemma-pi/node-myne/`. By the same pattern this file probably
> belongs in artoo's private working dir once one exists, not committed
> here in `node-artoo/` — Shane's call. Nothing in it is secret (no IPs,
> no credentials), so leaving it public isn't unsafe, just possibly
> inconsistent with the split.

## What this node is
The `artoo` Pi 5 hosts two distinct things that share hardware but are
architecturally separate — don't conflate them:

1. **The Gemma voice runtime** (`gemma_runtime.py`, systemd `gemma.service`,
   currently v18.2.x per git history) — real-time voice I/O: Gemini 2.5
   Flash Native Audio Live API over WebSocket, OpenWakeWord wake-word
   detection, TTS playback through the Anker PowerConf S500. This is the
   *voice* half — low-latency, always-listening, narrow in what it reasons
   about itself.
2. **Artoo, the reasoning agent** (Google's Antigravity CLI) — full-stack
   engineer persona (see `AGENTS.md` in this directory for its actual
   persona/protocol — that file, not this one, is what Antigravity CLI
   loads). Has shell access, Google Workspace tools, and is the thing that
   decides direct-execution vs. myne-cache vs. cloud-escalation for
   anything Gemma's voice pipeline hands off.

The **display is physically on artoo** — keep that in mind for anything
involving visual output/debugging UI, not just headless service work.

This node is NOT `myne` (separate Pi, Hailo-10H NPU, pure local
inference/RAG — see `node-myne/` and its own `CLAUDE.md` in myne's private
working dir). It is also not `satellite`/"slove" (Pi Zero 2W, mic-only
Wyoming-protocol satellite in the shed — no reasoning, just audio I/O).

## Models actually in play (verified against `available_models.md` in this
## repo and Shane's direct clarification, 2026-07-06 — don't trust older
## docs like `gemma_summary.md`, which is a stale June 8 2026 snapshot
## naming `gemini-flash-lite-latest`/plain "gemini-cli")
- `gemma_runtime.py` → `gemini-2.5-flash-native-audio-latest`. Confirmed
  current and correct — this is the only model in the family with
  `bidiGenerateContent` (live/voice) support. The Gemini 3.x line dropped
  live/voice capability in its latest releases, so voice must stay on 2.5.
- Artoo (Antigravity CLI) → Gemini 3.5 Flash / 3.1 Pro / 3.1 Flash-Lite —
  reasoning/tool-use models, no voice capability needed here since Artoo
  never touches raw audio.
- If you pull fresh docs on any of these, prefer them over this file or
  over anything dated before 2026-07-06 — model availability here moves
  fast (see the historical churn in `available_models.md`: 3.1 → 3.5 → the
  various preview tiers).

## Relationship to myne (the write-through cache loop)
Myne (separate Pi, port 9000) is Artoo's local knowledge base and a
write-through cache sitting between Artoo and any cloud escalation:
- Before escalating a non-system-function query to the cloud, Artoo should
  check `POST http://<myne-host>:9000/query` first (plain text in, plain
  text + hit/miss out — Artoo never embeds or touches vectors itself,
  myne does all of that internally).
- On a hit, use myne's answer directly — no cloud call needed.
- On a miss, escalate to the cloud as normal, then call
  `POST http://<myne-host>:9000/learn` with the query + the cloud's answer
  so the same/similar question is a local hit next time.
- This is layered *under* direct execution, not instead of it — per
  `AGENTS.md` Rule 9, the actual priority order is: direct execution
  (timers, lights, plugs — no reasoning needed) → myne cache check → cloud
  escalation. Myne is for queries that need real knowledge/reasoning, not
  device control.
- **Not yet verified**: whether Artoo's current code actually calls
  `/query`/`/learn` anywhere yet, or whether this is still aspirational
  per `AGENTS.md`'s Rule 9 wording ("determine first whether you can
  execute directly... then vectorize and check ChromaDB" — that phrasing
  describes an older direct-ChromaDB design, not the current myne
  HTTP-service design). Worth checking `artoo_tools.py` / whatever calls
  out to myne before assuming this loop is actually wired up end-to-end.

## Known debt: stale hardcoded paths from the pre-split architecture
`artoo_tools.py` (the copy now living in this directory, meant to run on
the physically separate artoo Pi) still hardcodes `/home/shane/google-labs/`
paths in multiple places — the shebang line, the Spotify subprocess call,
and the weight-tracker log path. Those paths were valid back when this
machine and myne were the same physical Pi (pre-split, when it was
hostnamed `gemma`); `google-labs` is now specifically myne's private
working directory and has no reason to exist on the artoo Pi post-split.
Git history shows an intent to fix this (`0589fec refactor hard coded
paths to prepare for migration to antigravity-cli`) that wasn't finished —
these three references survived that pass. Whatever artoo's own private
working directory ends up being named, `artoo_tools.py` needs its paths
repointed there, or centralized into `/config/` the way `light_control.py`
already was (`de8a2aa`). Confirm with Shane what that directory's name/path
actually is before fixing, rather than guessing.

## Repo / privacy split (per `AGENTS.md`'s existing Git & Privacy Protocol —
## repeated here for Claude Code's benefit, not redefining it)
- Public monorepo: `git@github.com:irish-bug/gemma-pi.git`, `node-artoo/`
  is this node's public slice — `AGENTS.md`, `gemma_runtime.py`,
  `artoo_tools.py`, `spotify_control.py`, service unit files, shell
  scripts.
- Private, never committed: `memory/`, `policies/`, `gemma_stable_env/`,
  `gemma_manifest.json`, `gemma_activity.log`, credentials/`.env` files —
  protected by `.gitignore`. `git status` before every push; if anything
  from those paths shows staged, stop and fix `.gitignore` first, don't
  just unstage and proceed.
- Per [[feedback_tests_before_commit]] on the myne side, Shane wants tests
  gating commits generally as of 2026-07-08 — confirm whether the same
  expectation applies here before committing anything from a Claude Code
  session in this directory; don't assume the myne-side rule silently
  covers artoo too.

## Hard rules carried over from `AGENTS.md` (do not relitigate — that file
## is authoritative for Artoo-the-agent's behavior; this is just so a
## Claude Code session doing engineering work here doesn't contradict them)
1. Never suggest X11/XQuartz forwarding.
2. Audio device selection is always per-node context — check
   `policies/INFRASTRUCTURE.md` for current mappings, never assume a
   device string is global across nodes.
3. Never volunteer PII from `gemma_manifest.json` in code/output destined
   for GitHub.
4. Respect the air-gap — home lab only, zero professional references.
5. Node awareness: voice I/O is Gemma's; reasoning/tools/shell are
   Artoo's; hardware access happens on whichever node physically has the
   hardware.
6. Markdown preservation — never delete existing headers/sections unless
   Shane explicitly directs it; append to the bottom of the relevant
   section rather than overwriting.

## What "done" looks like for Claude Code work in this directory
Genuinely open — unlike myne's CLAUDE.md, this one isn't backed by a
tracked implementation task in this session. Before taking on any
substantial change here (not just the path-debt cleanup above), check with
Shane what the actual current priority is — `TODO.md` at the repo root is
dated "v16.3" and reads as older/aspirational (R2D2 sound pack, `make`
hook wiring) rather than a live task list; don't treat it as current
without confirming.
