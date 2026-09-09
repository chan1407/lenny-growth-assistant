from pathlib import Path
import json
import re
import yaml


TRANSCRIPTS_DIR = Path("../data/transcripts/episodes")
OUTPUT_FILE = Path("../data/processed_chunks.json")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def parse_transcript(file_path: Path):
    """Read YAML frontmatter and transcript body."""

    content = file_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)

    if len(parts) != 3:
        return {}, content

    frontmatter_text = parts[1]
    body = parts[2].strip()

    try:
        metadata = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as error:
        print(f"Warning: YAML parsing failed for {file_path}")
        print(error)
        metadata = {}

    return metadata, body


def clean_text(text: str):
    """Clean unnecessary whitespace."""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str):
    """Split transcript into overlapping word-based chunks."""

    words = text.split()

    chunks = []
    start = 0

    while start < len(words):
        end = start + CHUNK_SIZE
        chunk = " ".join(words[start:end])

        if chunk.strip():
            chunks.append(chunk.strip())

        if end >= len(words):
            break

        start = end - CHUNK_OVERLAP

    return chunks


def process_transcript(file_path: Path):
    """Convert one transcript into searchable chunks."""

    metadata, transcript = parse_transcript(file_path)

    transcript = clean_text(transcript)
    chunks = chunk_text(transcript)

    results = []

    for index, chunk in enumerate(chunks):
        results.append(
            {
                "chunk_id": f"{file_path.parent.name}-{index}",
                "chunk_index": index,
                "text": chunk,
                "source": {
                    "guest": metadata.get("guest"),
                    "title": metadata.get("title"),
                    "youtube_url": metadata.get("youtube_url"),
                    "video_id": metadata.get("video_id"),
                    "publish_date": metadata.get("publish_date"),
                    "description": metadata.get("description"),
                    "keywords": metadata.get("keywords", []),
                    "file": str(file_path),
                },
            }
        )

    return results


def main():
    transcript_files = list(TRANSCRIPTS_DIR.rglob("transcript.md"))

    print(f"Found {len(transcript_files)} transcript files.")

    all_chunks = []

    for file_path in transcript_files:
        chunks = process_transcript(file_path)
        all_chunks.extend(chunks)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(
    all_chunks,
    ensure_ascii=False,
    indent=2,
    default=str,
),
        encoding="utf-8",
    )

    print(f"Total chunks: {len(all_chunks)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()