#!/home/shane/google-labs/gemma_stable_env/bin/python
# --- myne RAG store: shared ChromaDB access for rag_service.py / ingest.py ---
#
# One persistent Chroma client, three collections, one embedding function.
# Nothing in this file talks to the network (no hailo-ollama calls here) —
# it is pure storage/retrieval so rag_service.py can own the generation step.

import hashlib
import os

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "chroma_db")

# Chunking: these files are short hand-written markdown (policies, memory
# notes, transcripts), not long-form reference docs, so a small chunk size
# keeps each chunk topically coherent without fragmenting single sentences.
# Revisit if/when longer reference material (PDFs, full manuals) is ingested.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Cosine distance threshold below which a /query match counts as a "hit".
# Chroma reports cosine *distance* (0 = identical, 2 = opposite), not
# similarity. Measured directly against this node's actual `core`/`reference`
# content (short, informally-worded markdown): true matches landed in the
# 0.40-0.72 range (e.g. "what temperature unit" -> preferences.md at 0.50;
# "what is Shane's weight" -> HEALTH_PROTOCOL.md at 0.72), while clearly
# unrelated queries landed at 0.76+ (e.g. "recipe for chocolate cake" -> 0.83).
# There is no clean separation at the chunk level for short informal text —
# 0.75 sits in the gap and favors not missing a real hit. Re-measure if the
# corpus grows to include longer/more formal reference material, since that
# will shift the distribution.
HIT_DISTANCE_THRESHOLD = 0.75

_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Collections are configured for cosine distance explicitly. Chroma's
# default space (l2) is not comparable to the threshold above.
_COSINE_SPACE = {"hnsw:space": "cosine"}


def get_client():
    return chromadb.PersistentClient(path=DB_DIR)


def get_collections(client=None):
    """Returns (core, reference, learned_cache) collections, creating them if needed."""
    client = client or get_client()
    core = client.get_or_create_collection(
        name="core", embedding_function=_embedding_fn, metadata=_COSINE_SPACE
    )
    reference = client.get_or_create_collection(
        name="reference", embedding_function=_embedding_fn, metadata=_COSINE_SPACE
    )
    learned_cache = client.get_or_create_collection(
        name="learned_cache", embedding_function=_embedding_fn, metadata=_COSINE_SPACE
    )
    return core, reference, learned_cache


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    return splitter.split_text(text)


def stable_chunk_id(relpath: str, chunk_index: int) -> str:
    """Deterministic ID so re-ingesting the same file upserts instead of duplicating."""
    return f"{relpath}::chunk{chunk_index}"


def query_hash(query: str) -> str:
    """Deterministic ID for learned_cache entries, so re-learning the same
    query overwrites the old answer instead of accumulating duplicates."""
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
