from pathlib import Path
import json

import numpy as np
from sentence_transformers import SentenceTransformer


CHUNKS_FILE = Path("../data/processed_chunks.json")
EMBEDDINGS_FILE = Path("../data/embeddings.npy")

MODEL_NAME = "all-MiniLM-L6-v2"


def load_data():
    chunks = json.loads(
        CHUNKS_FILE.read_text(encoding="utf-8")
    )

    embeddings = np.load(EMBEDDINGS_FILE)

    model = SentenceTransformer(MODEL_NAME)

    return chunks, embeddings, model


def search(query, top_k=5):
    chunks, embeddings, model = load_data()

    query_embedding = model.encode(
        query,
        normalize_embeddings=True,
    )

    scores = embeddings @ query_embedding

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []

    for index in top_indices:
        results.append(
            {
                "score": float(scores[index]),
                "chunk": chunks[index],
            }
        )

    return results


if __name__ == "__main__":
    query = input("Ask a question: ")

    results = search(query)

    print("\nTop results:\n")

    for i, result in enumerate(results, start=1):
        chunk = result["chunk"]
        source = chunk["source"]

        print("=" * 80)
        print(f"Result {i}")
        print(f"Score: {result['score']:.4f}")
        print(f"Guest: {source.get('guest')}")
        print(f"Title: {source.get('title')}")
        print(f"YouTube: {source.get('youtube_url')}")
        print()
        print(chunk["text"][:1000])
        print()