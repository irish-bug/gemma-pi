#!/home/shane/google-labs/gemma_stable_env/bin/python
# --- myne RAG service: write-through local cache for Artoo's cloud escalations ---
#
# POST /query {"text": "..."}
#   -> {"hit": true,  "answer": "...", "source": "core|reference|learned_cache", "distance": 0.12}
#   -> {"hit": false} on a miss (NOT an http error — a miss is an expected,
#      valid outcome; Artoo escalates to the cloud itself and calls /learn).
#
# POST /learn {"query": "...", "answer": "..."}
#   -> {"stored": true}
#
# This service never calls the cloud. Artoo only ever sends/receives plain
# text — it never touches an embedding or a ChromaDB id.
#
# Query routing: rather than pre-deciding which collection is "right" for a
# given question, all three collections are queried and the single closest
# chunk (lowest cosine distance) wins. This keeps routing simple and lets
# embedding similarity do the work; revisit only if cross-collection
# candidates turn out to need different weighting.
#
# Hit behavior differs by collection:
#   - learned_cache hit -> the stored value IS already a full answer (it's a
#     previous cloud response), so it's returned directly with no NPU call.
#   - core/reference hit -> the stored value is a raw source chunk, so it's
#     used as grounding context for a fresh hailo-ollama generation.

import os
import time

import requests
from fastapi import FastAPI
from pydantic import BaseModel

from rag_store import HIT_DISTANCE_THRESHOLD, get_client, get_collections, query_hash

HAILO_OLLAMA_URL = "http://127.0.0.1:8000/api/chat"
# llama3.2:3b chosen over qwen2.5-instruct:1.5b for generation. Initially
# picked qwen for its smaller size (less latency), but direct A/B testing
# against this node's real hailo-ollama models showed qwen2.5-instruct:1.5b
# fails simple grounded-extraction ("Temperature Unit: Fahrenheit" in context
# -> qwen answered "context does not contain the answer"; llama3.2:3b
# answered "Fahrenheit" correctly on the same input). Correctness over
# latency for a Pi-scale cache lookup.
GENERATION_MODEL = "llama3.2:3b"

app = FastAPI()

_client = get_client()
_core, _reference, _learned_cache = get_collections(_client)
_COLLECTIONS = {"core": _core, "reference": _reference, "learned_cache": _learned_cache}


class QueryRequest(BaseModel):
    text: str


class LearnRequest(BaseModel):
    query: str
    answer: str


def _best_match(text: str):
    """Queries all three collections, returns the single closest chunk across
    all of them, or None if every collection is empty."""
    best = None
    for name, collection in _COLLECTIONS.items():
        if collection.count() == 0:
            continue
        result = collection.query(query_texts=[text], n_results=1)
        docs = result.get("documents", [[]])[0]
        if not docs:
            continue
        distance = result["distances"][0][0]
        if best is None or distance < best["distance"]:
            best = {
                "collection": name,
                "document": docs[0],
                "distance": distance,
                "metadata": result["metadatas"][0][0],
            }
    return best


def _generate_grounded_answer(question: str, context: str) -> str | None:
    """Returns the generated answer, or None if hailo-ollama fails/times out.
    A None here is treated by the caller as a miss (not an HTTP error) so
    Artoo's existing escalate-on-miss path handles it without new logic."""
    system_instruction = (
        "You are Myne Jr., an intelligent local AI. "
        "Answer the user's question using ONLY the provided context. "
        "If the context does not contain the answer, say you don't know. "
        "Be concise and do not use markdown formatting.\n\n"
        f"CONTEXT:\n{context}"
    )
    payload = {
        "model": GENERATION_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": question},
        ],
        "stream": False,
    }
    try:
        response = requests.post(HAILO_OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[!] hailo-ollama generation failed, treating as miss: {e}")
        return None
    return response.json().get("message", {}).get("content", "").strip()


@app.post("/query")
def query(req: QueryRequest):
    match = _best_match(req.text)
    if match is None or match["distance"] > HIT_DISTANCE_THRESHOLD:
        return {"hit": False}

    if match["collection"] == "learned_cache":
        answer = match["metadata"]["answer"]
    else:
        answer = _generate_grounded_answer(req.text, match["document"])
        if answer is None:
            return {"hit": False}

    return {
        "hit": True,
        "answer": answer,
        "source": match["collection"],
        "distance": match["distance"],
    }


@app.post("/learn")
def learn(req: LearnRequest):
    # learned_at powers evict_cache.py's staleness sweep (see that file) —
    # written here rather than left for eviction to infer, since eviction
    # has no other reliable signal for when a cloud answer was cached.
    _learned_cache.upsert(
        ids=[query_hash(req.query)],
        documents=[req.query],
        metadatas=[{"answer": req.answer, "learned_at": time.time()}],
    )
    return {"stored": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
