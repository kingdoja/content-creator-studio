from typing import List


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    clean = (text or "").strip()
    if not clean:
        return []

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 5)

    chunks: List[str] = []
    step = max(1, chunk_size - chunk_overlap)
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunks.append(clean[start:end])
        if end >= len(clean):
            break
        start += step
    return chunks
