#!/home/shane/google-labs/gemma_stable_env/bin/python
# --- myne RAG: learned_cache staleness/eviction sweep ---
#
# Only touches learned_cache — core/reference are hand-curated and have no
# concept of staleness (per CLAUDE.md's schema-isolation requirement, this
# was deliberately kept out of rag_store.py/ingest.py).
#
# Two independent passes, in order:
#   1. TTL sweep — delete anything older than TTL_SECONDS. Cloud answers can
#      go stale (facts change), and we have no way to know which ones did,
#      so age is the only signal available. 30 days is a starting guess, not
#      a measured value (unlike the distance threshold in rag_store.py) —
#      there's no usage history yet to calibrate against. Revisit once real
#      /learn traffic accumulates.
#   2. Size cap — if still over MAX_ENTRIES after the TTL sweep, delete the
#      oldest entries until back under the cap. This bounds worst-case growth
#      on a Pi's disk even if TTL alone isn't aggressive enough.
#
# Entries written before learned_at existed (or any entry missing it for any
# other reason) are treated as expired rather than kept indefinitely —
# there's no way to know their true age, and an unknown-age cache entry is a
# stale-answer risk we'd rather not silently keep around.
#
# LRU (evicting by last-access instead of/alongside write time) was
# considered and skipped: it would require updating metadata on every /query
# hit, adding a write on the hot read path for a benefit that's unverifiable
# without real traffic. TTL + size cap is simpler and sufficient for now.
#
# Safe to re-run any time (e.g. from a daily systemd timer) — a no-op pass
# just deletes nothing.

import time

from rag_store import get_client, get_collections

TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
MAX_ENTRIES = 1000


def sweep():
    client = get_client()
    _core, _reference, learned_cache = get_collections(client)

    total = learned_cache.count()
    if total == 0:
        print("[*] learned_cache: empty, nothing to sweep.")
        return

    data = learned_cache.get(include=["metadatas"])
    now = time.time()
    ages = []
    for entry_id, metadata in zip(data["ids"], data["metadatas"]):
        learned_at = metadata.get("learned_at")
        ages.append((entry_id, learned_at))

    expired_ids = [
        entry_id
        for entry_id, learned_at in ages
        if learned_at is None or (now - learned_at) > TTL_SECONDS
    ]
    if expired_ids:
        learned_cache.delete(ids=expired_ids)
        print(f"[*] learned_cache: evicted {len(expired_ids)} expired entr(ies) (TTL).")

    remaining = [
        (entry_id, learned_at)
        for entry_id, learned_at in ages
        if entry_id not in set(expired_ids)
    ]
    overflow = len(remaining) - MAX_ENTRIES
    if overflow > 0:
        remaining.sort(key=lambda pair: (pair[1] is None, pair[1] or 0))
        oldest_ids = [entry_id for entry_id, _ in remaining[:overflow]]
        learned_cache.delete(ids=oldest_ids)
        print(f"[*] learned_cache: evicted {len(oldest_ids)} oldest entr(ies) (size cap).")

    if not expired_ids and overflow <= 0:
        print(f"[*] learned_cache: {total} entr(ies), nothing to evict.")


if __name__ == "__main__":
    sweep()
