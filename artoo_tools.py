#!/home/shane/google-labs/gemma_stable_env/bin/python
# --- v3.0.0 Artoo Execution Tools (Node-Aware Dispatcher) ---
# CHANGELOG:
# - v3.0.0: Replaced the hardcoded raw-shell safelist (uptime/date/whoami/...
#   plus a "restart gemma" special case) with the reasoning-escalation path
#   CLAUDE.md already described but that wasn't actually wired end to end
#   (see README's "Agentic caching" section): anything that isn't Spotify,
#   Home Assistant, or weight logging now checks Myne Jr's local cache
#   (POST /query) first, and on a miss hands the raw command off to the real
#   Artoo reasoning agent -- a one-shot `agy --print` call, not a hardcoded
#   Python if/elif tree pretending to be one -- then writes the answer back
#   via POST /learn so the same question is a local hit next time. Artoo now
#   runs with real (--dangerously-skip-permissions) shell access for
#   anything Gemma doesn't recognize as simple device control, matching how
#   artoo.service already runs the interactive session. Spotify/Home
#   Assistant/weight-logging routing is unchanged -- those stay fast local
#   paths per CLAUDE.md's routing description, they don't need a reasoning
#   agent round-trip.
#
# - v2.1.1: Fixed weight logging crash — added missing `import os` and replaced
#   fragile __file__-based path resolution with absolute path to weight_tracker.txt.
#   The weight logging section now reads numeric values from user commands and
#   appends dated entries to /home/shane/google-labs/memory/weight_tracker.txt.
#
# - v2.1.0: Patched the subprocess Spotify handoff. The target_node variable is now
#   explicitly passed as sys.argv[2] to spotify_control.py, preventing the default
#   "local" override bug. Added subprocess.STDOUT capture so Gemma can read playback
#   errors.
#
# - v2.0.0: Refactored dispatcher to support 'target_node' routing for Home
#   Assistant (tinytuya/kasa) and Spotify.

import subprocess
import json
import re
import os
from datetime import datetime

import requests

# Node connection info (Myne Jr's address, etc.) is real infrastructure data
# and lives in the gitignored config/nodes.json, not in this file -- see
# CLAUDE.md's public/private split.
NODE_CONFIG_PATH = "/home/shane/google-labs/config/nodes.json"

AGY_BIN = "/home/shane/.local/bin/agy"
AGY_MODEL = "Claude Sonnet 4.6 (Thinking)"
AGY_WORKDIR = "/home/shane/google-labs"
AGY_TIMEOUT_S = 300


def _myne_url(path: str) -> str | None:
    """Resolves a Myne Jr endpoint URL from the local node config. Returns
    None if the config isn't present yet -- expected on a node that hasn't
    had its private config supplied (see CLAUDE.md), and treated the same
    as Myne being unreachable by callers."""
    try:
        with open(NODE_CONFIG_PATH) as f:
            myne = json.load(f)["myne"]
        return f"http://{myne['host']}:{myne['port']}{path}"
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None


def query_myne_cache(command: str) -> str | None:
    """Checks Myne Jr's local RAG cache before paying for an Artoo/cloud
    round-trip. Returns the cached answer on a hit, or None on a miss OR if
    Myne is unreachable -- rag_service.py's /query contract treats a miss as
    an expected outcome, not an error, and callers here escalate to Artoo
    either way."""
    url = _myne_url("/query")
    if url is None:
        return None
    try:
        response = requests.post(url, json={"text": command}, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[!] Myne Jr unreachable, escalating directly: {e}")
        return None
    data = response.json()
    return data["answer"] if data.get("hit") else None


def learn_myne_cache(command: str, answer: str) -> None:
    """Writes an Artoo answer back into Myne's learned_cache so the same
    question is a local hit next time. Best-effort: a failure here shouldn't
    take down a response Gemma already has to speak."""
    url = _myne_url("/learn")
    if url is None:
        return
    try:
        requests.post(url, json={"query": command, "answer": answer}, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"[!] Failed to write back to Myne Jr cache: {e}")


def build_artoo_prompt(command: str, target_node: str) -> str:
    """Frames the raw voice command with the context Artoo needs to act on
    it: which node it came from, and that the reply goes straight to TTS so
    it needs to stay concise, markdown-free plain text."""
    user_context = os.environ.get("USER_CONTEXT", "User is a human interacting via voice.")
    return (
        f"{user_context}\n"
        f"Gemma received this voice command on the '{target_node}' hardware node "
        f"and is escalating it to you because it needs real reasoning, not just "
        f"device control: \"{command}\"\n"
        "Reply with a concise, plain-text answer only -- it will be spoken aloud "
        "via text-to-speech, so no markdown."
    )


def escalate_to_artoo(command: str, target_node: str) -> str | None:
    """Hands the command to the real Artoo reasoning agent (agy) as a
    one-shot, non-interactive call -- `--print` exists specifically for
    this, as opposed to the persistent interactive tmux session artoo.service
    keeps running for Shane's own terminal use. Runs from AGY_WORKDIR so
    agy's cwd is the workspace root containing AGENTS.md (same requirement
    noted in artoo.service), and --dangerously-skip-permissions since
    there's no human here to approve tool calls.

    Returns None on failure/timeout rather than an error string -- the
    caller must not write a failure into Myne's learned_cache as if it were
    a real answer."""
    prompt = build_artoo_prompt(command, target_node)
    try:
        output = subprocess.check_output(
            [
                AGY_BIN, "--print", prompt,
                "--model", AGY_MODEL,
                "--dangerously-skip-permissions",
                "--add-dir", f"{AGY_WORKDIR}/memory/",
                "--add-dir", f"{AGY_WORKDIR}/policies/",
            ],
            cwd=AGY_WORKDIR,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=AGY_TIMEOUT_S,
        )
        return output.strip()
    except subprocess.CalledProcessError as e:
        error_msg = e.output.strip() if e.output else str(e)
        print(f"[!] Artoo execution failed: {error_msg}")
        return None
    except subprocess.TimeoutExpired:
        print("[!] Artoo did not respond in time.")
        return None


def escalate_with_cache(command: str, target_node: str) -> str:
    """Myne-first, Artoo-on-miss, write-through-cache-after. A failed Artoo
    call is reported back but deliberately never reaches learn_myne_cache --
    caching an error would poison every future identical query until
    evict_cache.py's TTL sweep caught up with it."""
    cached = query_myne_cache(command)
    if cached is not None:
        print(f"⚡ [SYS] Myne Jr cache hit for: '{command}'")
        return cached

    print(f"⚡ [SYS] Myne Jr miss, escalating to Artoo: '{command}'")
    answer = escalate_to_artoo(command, target_node)
    if answer is None:
        return "Sorry, Artoo didn't respond -- try that again in a moment."

    learn_myne_cache(command, answer)
    return answer


def local_artoo_executor(command: str, target_node: str = "local") -> str:
    """
    Artoo's master execution router.
    Takes a plain text command and a target hardware node from Gemma and routes it
    to the correct local Python script, API, or -- for anything beyond simple
    device control -- the real Artoo reasoning agent.
    """
    command = command.lower().strip()

    # --- 1. SPOTIFY ROUTING ---
    if "play" in command or "stop" in command or "pause" in command:
        print(f"⚡ [SYS] Artoo routing Spotify API request to {target_node.upper()}: '{command}'")
        try:
            # FIX (v2.1.0): target_node is now explicitly passed as the third argument
            output = subprocess.check_output(
                [
                    "/home/shane/google-labs/gemma_stable_env/bin/python",
                    "/home/shane/google-labs/spotify_control.py",
                    command,
                    target_node
                ],
                stderr=subprocess.STDOUT,
                text=True
            )
            return output.strip()

        except subprocess.CalledProcessError as e:
            # If the Spotify script exits with an error (e.g., 404, Device Offline),
            # this captures the exact print statement and feeds it back to Gemma's brain.
            error_msg = e.output.strip() if e.output else str(e)
            print(f"[!] Artoo Execution Failed: {error_msg}")
            return f"Error executing Spotify command: {error_msg}"

    # --- 2. HOME ASSISTANT ROUTING (Tinytuya / Kasa) ---
    # As per HOME_ASSISTANT.md policy, Artoo handles these locally without cloud APIs
    elif "light" in command or "plug" in command or "turn" in command:
        print(f"⚡ [SYS] Artoo routing Home Assistant request: '{command}'")
        return f"Simulated Home Assistant success for command: {command}"

    # --- 3. DEDICATED LOCAL WEIGHT LOGGING ---
    elif "weight" in command or "weigh" in command or "pound" in command or "lbs" in command:
        try:
            match = re.search(r'\d+(\.\d+)?', command)
            if match:
                weight_val = match.group()
                date_str = datetime.now().strftime("%m/%d/%Y")
                log_entry = f"{date_str}: {weight_val} lbs"
                # FIX (v2.1.1): Use absolute path instead of __file__-based resolution
                # to avoid path fragility across subprocess contexts.
                file_path = "/home/shane/google-labs/memory/weight_tracker.txt"
                with open(file_path, "a") as f:
                    f.write(log_entry + "\n")
                print(f"⚡ [SYS] Artoo logged weight to {file_path}: {log_entry}")
                return f"Successfully logged weight: {weight_val} lbs."
            else:
                return "Artoo failed: Could not detect a valid number in the weight command."
        except Exception as e:
            return f"Error logging weight: {str(e)}"

    # --- 4. ESCALATE TO ARTOO (anything needing real reasoning, not device control) ---
    else:
        return escalate_with_cache(command, target_node)
