from pathlib import Path
import json

import numpy as np
from sentence_transformers import SentenceTransformer


REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_FILE = REPO_ROOT / "data" / "processed_chunks.json"
EMBEDDINGS_FILE = REPO_ROOT / "data" / "embeddings.npy"

MODEL_NAME = "all-MiniLM-L6-v2"

_chunks = None
_embeddings = None
_model = None


def load_retriever():
    global _chunks, _embeddings, _model

    if _chunks is not None:
        return

    print("Loading retrieval data...")

    _chunks = json.loads(
        CHUNKS_FILE.read_text(encoding="utf-8")
    )

    _embeddings = np.load(EMBEDDINGS_FILE)

    _model = SentenceTransformer(MODEL_NAME)

    print(f"Loaded {len(_chunks)} chunks.")


def search(query: str, top_k: int = 5):
    load_retriever()

    query_embedding = _model.encode(
        query,
        normalize_embeddings=True,
    )

    scores = _embeddings @ query_embedding

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []

    for index in top_indices:
        chunk = _chunks[index]
        source = chunk["source"]

        results.append(
            {
                "score": round(float(scores[index]), 4),
                "text": chunk["text"],
                "source": {
                    "guest": source.get("guest"),
                    "title": source.get("title"),
                    "youtube_url": source.get("youtube_url"),
                    "publish_date": source.get("publish_date"),
                },
            }
        )

    return results