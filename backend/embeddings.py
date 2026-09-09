from pathlib import Path
import json

import numpy as np
from sentence_transformers import SentenceTransformer


INPUT_FILE = Path("../data/processed_chunks.json")
OUTPUT_FILE = Path("../data/embeddings.npy")

MODEL_NAME = "all-MiniLM-L6-v2"


def main():
    print("Loading chunks...")

    chunks = json.loads(
        INPUT_FILE.read_text(encoding="utf-8")
    )

    texts = [chunk["text"] for chunk in chunks]

    print(f"Found {len(texts)} chunks.")
    print(f"Loading embedding model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)

    print("Creating embeddings...")
    
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    np.save(OUTPUT_FILE, embeddings)

    print()
    print(f"Embedding shape: {embeddings.shape}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()