import re
from typing import List, Dict, Any
from ..config import settings


class Chunk:
    def __init__(self, chunk_id: str, document_id: str, page_number: int, text: str):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.page_number = page_number
        self.text = text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "text": self.text,
        }


class ChunkingService:
    @staticmethod
    def _split_into_atomic_segments(text: str, max_segment_size: int) -> List[str]:
        """
        Decomposes page text hierarchically into atomic units:
        paragraphs -> sentences -> word-boundary slices.
        Guarantees that no single segment exceeds max_segment_size.
        """
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        segments: List[str] = []

        for para in paragraphs:
            if len(para) <= max_segment_size:
                segments.append(para)
                continue

            # Split large paragraph by sentence boundaries
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
            for sent in sentences:
                if len(sent) <= max_segment_size:
                    segments.append(sent)
                    continue

                # Single sentence exceeds max_segment_size, slice by word boundaries
                words = sent.split()
                current_slice: List[str] = []
                current_len = 0

                for word in words:
                    if current_len + len(word) + 1 <= max_segment_size:
                        current_slice.append(word)
                        current_len += len(word) + 1
                    else:
                        if current_slice:
                            segments.append(" ".join(current_slice))
                        # If a single word is somehow gigantic, slice characters
                        if len(word) > max_segment_size:
                            for i in range(0, len(word), max_segment_size):
                                segments.append(word[i : i + max_segment_size])
                            current_slice = []
                            current_len = 0
                        else:
                            current_slice = [word]
                            current_len = len(word)

                if current_slice:
                    segments.append(" ".join(current_slice))

        return segments

    @classmethod
    def chunk_document(
        cls,
        document_id: str,
        pages: List[Dict[str, Any]],
        chunk_size: int = None,
        chunk_overlap: int = None,
    ) -> List[Chunk]:
        """
        Chunks extracted pages while strictly preserving 1-based page metadata.
        Splits text into overlapping chunks respecting paragraph, sentence, and word boundaries.
        Guarantees non-empty chunks and deterministic ordering.
        """
        chunk_size = chunk_size or settings.CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        chunks: List[Chunk] = []
        chunk_index = 0

        for page in pages:
            page_num = page.get("page_number", 1)
            page_text = (page.get("text") or "").strip()
            if not page_text:
                continue

            # Break page into atomic units that individually fit within chunk_size
            segments = cls._split_into_atomic_segments(page_text, max_segment_size=chunk_size)
            if not segments:
                continue

            current_chunk_text = ""

            for segment in segments:
                if not current_chunk_text:
                    current_chunk_text = segment
                elif len(current_chunk_text) + len(segment) + 1 <= chunk_size:
                    # Append segment with a newline or space separator
                    separator = "\n\n" if "\n" not in segment else " "
                    current_chunk_text += separator + segment
                else:
                    # Flush current chunk
                    if current_chunk_text.strip():
                        chunks.append(
                            Chunk(
                                chunk_id=f"chunk_{chunk_index}",
                                document_id=document_id,
                                page_number=page_num,
                                text=current_chunk_text.strip(),
                            )
                        )
                        chunk_index += 1

                    # Compute overlap from the trailing portion of the flushed chunk
                    if chunk_overlap > 0 and len(current_chunk_text) > chunk_overlap:
                        overlap_candidate = current_chunk_text[-chunk_overlap:]
                        # Snap to the nearest word boundary
                        first_space = overlap_candidate.find(" ")
                        if first_space != -1 and first_space < len(overlap_candidate) - 1:
                            overlap = overlap_candidate[first_space + 1 :].strip()
                        else:
                            overlap = overlap_candidate.strip()
                        current_chunk_text = (overlap + " " + segment).strip()
                    else:
                        current_chunk_text = segment

            # Flush final leftover text for the page
            if current_chunk_text.strip():
                chunks.append(
                    Chunk(
                        chunk_id=f"chunk_{chunk_index}",
                        document_id=document_id,
                        page_number=page_num,
                        text=current_chunk_text.strip(),
                    )
                )
                chunk_index += 1

        return chunks
