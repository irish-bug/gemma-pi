#!/home/shane/google-labs/gemma_stable_env/bin/python
# --- myne RAG ingestion: populates core + reference collections ---
#
# Safe to re-run any time (upsert on deterministic chunk IDs) — e.g. after
# editing a memory or policy file. Does NOT touch learned_cache; that
# collection only grows via rag_service.py's /learn endpoint.
#
# Design decision: "core" = hand-curated files that change often (memory/
# policies) — Shane edits these directly and expects re-ingestion to pick up
# edits. "reference" = the static background corpus (transcripts/session_logs,
# plus — as of 2026-07-06 — the "Rozemyne" NotebookLM doc dump at
# /home/shane/Documents/myne_docs/notebooklm_docs_from_rozemyne, which is the
# "better home" for reference docs the original comment here said to revisit
# for. REFERENCE_DIRS entries may be absolute paths outside this repo;
# os.path.join(BASE_DIR, d) resolves correctly either way since
# os.path.join discards BASE_DIR when d is already absolute.
#
# The Rozemyne dump is large and heterogeneous (PDFs, HTML, plain markdown,
# a couple of full git-cloned repos, some genuinely wrong-machine debug logs).
# It was hand-triaged with Shane before writing this, file by file — this is
# NOT "ingest the whole directory tree." Specifically:
#   - Only the dump's top-level files are swept (non-recursive), same as
#     every other REFERENCE_DIRS entry, EXCLUDE_BASENAMES below removes a
#     handful of bad ones from that sweep.
#   - hailo_model_zoo/ (computer-vision benchmarks — this node only runs
#     text-generation models, no CV workload) and modelcontextprotocol/ +
#     mcp_2_0_specification.txt (nothing in this repo uses MCP yet — Shane
#     said skip for now, revisit once Antigravity/MCP is actually wired up)
#     are deliberately NOT in REFERENCE_DIRS at all.
#   - hailo_model_zoo_genai/ (the GenAI-specific repo clone) IS relevant —
#     but again only specific subfolders, not the whole clone: the top-level
#     docs (README/MODELS/USAGE/CHANGELOG) plus per-model manifest.json files
#     for the five models actually pulled via hailo-ollama (checked live via
#     /api/tags on 2026-07-06: deepseek_r1_distill_qwen, llama3.2, qwen2,
#     qwen2.5, qwen2.5-coder). mike_plan_for_notebooklm_rozemyne.md (in the
#     dump) recommended a similar but not identical slice (it named qwen3 and
#     whisper manifests, neither of which is actually pulled) — Shane's call
#     was to match currently-pulled models instead of following that plan
#     verbatim. Note the llama3.2 manifest found here says parameter_size
#     "1B", but the live hailo-ollama tag is llama3.2:3b — this dump is a
#     point-in-time snapshot, not live truth; that's expected for a "static"
#     reference collection, not a bug to fix here.
#
# EXCLUDE_BASENAMES reasons (checked content, not just filenames):
#   - gemini_debugs_audio.md / .ini (byte-identical): a terminal capture
#     debugging audio on a machine hostnamed "atarivcs" (Intel SOF firmware,
#     snap/Firefox apparmor denials) — wrong machine entirely, not myne/artoo.
#   - gemma_packaging_spec_master.md: an HTTrack-saved HTML page, almost
#     entirely raw <table>/<div> markup, not prose.
#   - pi5_hardware_master_spec.txt: a stub with empty section headers; its
#     _FINAL sibling has the real content.
#   - Gemini 3.1 Flash Live Preview.md, gemini_31_ga_specs.md: both raw
#     ai.google.dev scrapes (nav menus, inline base64 SVGs) describing Gemini
#     3.1's now-dropped live/voice capability — superseded by the clean
#     freshly-fetched *_fetched_2026-07-06.md files in the same directory.
#   - artoo_myne_intro.md, mike_plan_for_notebooklm_rozemyne.md: chat-log
#     narrative/meta-planning, not fact material to ground Q&A against.
#   - mcp_2_0_specification.txt: see modelcontextprotocol note above.

import glob
import os
from html.parser import HTMLParser

from pypdf import PdfReader

from rag_store import _COSINE_SPACE, _embedding_fn, chunk_text, get_client, get_collections, stable_chunk_id

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROZEMYNE_DIR = "/home/shane/Documents/myne_docs/notebooklm_docs_from_rozemyne"

CORE_DIRS = ["memory", "policies"]
REFERENCE_DIRS = [
    "transcripts",
    "session_logs",
    ROZEMYNE_DIR,
    os.path.join(ROZEMYNE_DIR, "hailo_model_zoo_genai"),
    os.path.join(ROZEMYNE_DIR, "hailo_model_zoo_genai", "docs"),
    os.path.join(ROZEMYNE_DIR, "hailo_model_zoo_genai", "models", "manifests", "deepseek_r1", "1.5b"),
    os.path.join(ROZEMYNE_DIR, "hailo_model_zoo_genai", "models", "manifests", "llama3.2", "1b"),
    os.path.join(ROZEMYNE_DIR, "hailo_model_zoo_genai", "models", "manifests", "qwen2", "1.5b"),
    os.path.join(ROZEMYNE_DIR, "hailo_model_zoo_genai", "models", "manifests", "qwen2.5", "1.5b"),
    os.path.join(ROZEMYNE_DIR, "hailo_model_zoo_genai", "models", "manifests", "qwen2.5-coder", "1.5b"),
]

EXCLUDE_BASENAMES = {
    "gemini_debugs_audio.md",
    "gemini_debugs_audio.ini",
    "gemma_packaging_spec_master.md",
    "pi5_hardware_master_spec.txt",
    "Gemini 3.1 Flash Live Preview.md",
    "gemini_31_ga_specs.md",
    "artoo_myne_intro.md",
    "mike_plan_for_notebooklm_rozemyne.md",
    "mcp_2_0_specification.txt",
    # Saved Gemini web-app chat page — its sidebar nav drags in titles from
    # unrelated personal chats (weight tracking, shed flooring, EV
    # conversion, etc.) alongside the actual Gemma-project conversation, and
    # the conversation itself is narrative/meta like the two entries above.
    "Gemma speaks - Google Gemini.html",
    # Build tooling that lives at the root of the hailo_model_zoo_genai
    # clone alongside the docs we actually want (README.rst etc.) — not
    # documentation.
    "CMakeLists.txt",
}

# Plain-text-ish formats read directly; PDF/HTML need real extraction.
TEXT_EXTENSIONS = (".md", ".txt", ".rst", ".json")
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS + (".pdf", ".html")


class _HTMLTextExtractor(HTMLParser):
    """Crude tag-stripping text extractor — no nav/boilerplate filtering.
    Good enough for the two standalone article/wiki pages this pulls in;
    deliberately not built out further since there was no case needing it
    (see EXCLUDE_BASENAMES — the messier doc-site scrapes were dropped
    entirely rather than cleaned)."""

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.chunks.append(text)


def _load_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTENSIONS:
        with open(path, "r", errors="ignore") as f:
            return f.read()
    if ext == ".pdf":
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == ".html":
        parser = _HTMLTextExtractor()
        with open(path, "r", errors="ignore") as f:
            parser.feed(f.read())
        return "\n".join(parser.chunks)
    raise ValueError(f"Unsupported extension: {ext}")


def _corpus_files(dirs):
    files = []
    for d in dirs:
        base = os.path.join(BASE_DIR, d)
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(glob.glob(os.path.join(base, f"*{ext}")))
    files = [f for f in files if os.path.basename(f) not in EXCLUDE_BASENAMES]
    return sorted(files)


# Bounds peak memory of any single upsert() call. Found the hard way: a
# prior run accumulated every chunk across an entire REFERENCE_DIRS sweep
# (34,786 chunks, 93% from one 12MB file) into one Python list and issued
# one upsert() at the very end — silently OOM-killed on this Pi (7.9GB RAM,
# shared with the always-on rag_service.py embedding model) with zero
# Python-side traceback. Batching bounds memory to BATCH_SIZE chunks
# regardless of how large a single source file is, and means a kill only
# loses the in-flight batch instead of the entire run.
BATCH_SIZE = 500


def ingest_dirs(collection, dirs, label):
    files = _corpus_files(dirs)
    if not files:
        print(f"[*] No files found for {label} in {dirs}", flush=True)
        return

    ids, documents, metadatas = [], [], []
    total_upserted = 0
    files_seen = 0

    def _flush():
        nonlocal ids, documents, metadatas, total_upserted
        if not ids:
            return
        # upsert (not add) so re-running after an edit overwrites the old
        # chunk content at the same ID instead of raising on duplicate IDs.
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        total_upserted += len(ids)
        print(f"[*] {label}: upserted batch of {len(ids)} chunks (running total {total_upserted})", flush=True)
        ids, documents, metadatas = [], [], []

    for path in files:
        relpath = os.path.relpath(path, BASE_DIR)
        try:
            text = _load_text(path)
        except Exception as e:
            print(f"[!] {label}: failed to load {relpath}: {e}", flush=True)
            continue
        if not text.strip():
            continue
        files_seen += 1
        for i, chunk in enumerate(chunk_text(text)):
            ids.append(stable_chunk_id(relpath, i))
            documents.append(chunk)
            metadatas.append({"source": relpath, "chunk_index": i})
            if len(ids) >= BATCH_SIZE:
                _flush()

    _flush()

    if total_upserted == 0:
        print(f"[*] {label}: nothing to ingest (all files empty).", flush=True)
        return

    print(f"[*] {label}: upserted {total_upserted} chunks from {files_seen} file(s) total.", flush=True)

    # Verify against the persisted store itself, not just "upsert() didn't
    # raise" — a prior run printed full success for all batches yet a
    # fresh process afterward found the collection unchanged (no exception,
    # no repro found after extensive testing; cause unconfirmed). Re-opening
    # a fresh client here catches that class of silent loss immediately
    # instead of relying on a separate manual check after the fact.
    fresh_count = get_client().get_or_create_collection(
        name=collection.name, embedding_function=_embedding_fn, metadata=_COSINE_SPACE
    ).count()
    print(f"[*] {label}: persisted count via fresh connection = {fresh_count}", flush=True)


def main():
    client = get_client()
    core, reference, _learned_cache = get_collections(client)
    ingest_dirs(core, CORE_DIRS, "core")
    ingest_dirs(reference, REFERENCE_DIRS, "reference")
    print("[*] ingest.py: done.", flush=True)


if __name__ == "__main__":
    main()
