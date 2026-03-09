from __future__ import annotations

def chunkText(text: str, chunk_size: int = 250, overlap: int = 250) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    Why word-based and not character-based? The embedding model's limit
    is measured in tokens (roughly words), so word count is a better
    proxy than character count.

    chunk_size: target number of words per chunk
    overlap: number of words to repeat at the start of the next chunk
    """

    if not text or not text.strip():
        return []
    
    words = text.split()

    if len(words) <= chunk_size: #if doc fits inside one chunk, just return it as-is
        return [text]
    
    chunks = []
    step = chunk_size - overlap

    for start in range(0, len(words), step):
        end = start + chunk_size
        chunkWords = words[start:end]
        chunks.append(" ".join(chunkWords))

        if end >= len(words):
            break

    return chunks