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
    def chunk_document(
        document_id: str,
        pages: List[Dict[str, Any]],
        chunk_size: int = None,
        chunk_overlap: int = None,
    ) -> List[Chunk]:
        """
        Chunks extracted pages while preserving 1-based page metadata.
        Splits text into overlapping chunks, respecting paragraph and sentence boundaries.
        """
        chunk_size = chunk_size or settings.CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        chunks: List[Chunk] = []
        chunk_index = 0

        for page in pages:
            page_num = page["page_number"]
            page_text = page["text"].strip()
            if not page_text:
                continue

            # Split by paragraphs first
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]

            current_chunk = ""
            for para in paragraphs:
                # If paragraph fits into current chunk, add it
                if not current_chunk:
                    current_chunk = para
                elif len(current_chunk) + len(para) + 1 <= chunk_size:
                    current_chunk += "\n\n" + para
                else:
                    # Current chunk is full or adding paragraph would exceed chunk_size
                    if len(current_chunk) >= chunk_size:
                        # Flush current chunk
                        chunks.append(
                            Chunk(
                                chunk_id=f"chunk_{chunk_index}",
                                document_id=document_id,
                                page_number=page_num,
                                text=current_chunk.strip(),
                            )
                        )
                        chunk_index += 1

                        # Compute overlap from the end of current_chunk
                        overlap_text = (
                            current_chunk[-chunk_overlap:]
                            if len(current_chunk) > chunk_overlap
                            else current_chunk
                        )
                        # Try to find word boundary for overlap
                        space_idx = overlap_text.find(" ")
                        if space_idx != -1 and space_idx < len(overlap_text) - 1:
                            overlap_text = overlap_text[space_idx + 1 :]

                        current_chunk = overlap_text + "\n\n" + para
                    else:
                        # Para itself might be very large, split it by sentences
                        sentences = re.split(r"(?<=[.!?])\s+", para)
                        for sent in sentences:
                            sent = sent.strip()
                            if not sent:
                                continue
                            if len(current_chunk) + len(sent) + 1 <= chunk_size:
                                current_chunk += (" " if current_chunk else "") + sent
                            else:
                                if current_chunk.strip():
                                    chunks.append(
                                        Chunk(
                                            chunk_id=f"chunk_{chunk_index}",
                                            document_id=document_id,
                                            page_number=page_num,
                                            text=current_chunk.strip(),
                                        )
                                    )
                                    chunk_index += 1
                                    overlap_text = (
                                        current_chunk[-chunk_overlap:]
                                        if len(current_chunk) > chunk_overlap
                                        else current_chunk
                                    )
                                    current_chunk = overlap_text + " " + sent
                                else:
                                    # Single sentence longer than chunk_size, slice by characters
                                    start = 0
                                    while start < len(sent):
                                        end = start + chunk_size
                                        sub_slice = sent[start:end].strip()
                                        if sub_slice:
                                            chunks.append(
                                                Chunk(
                                                    chunk_id=f"chunk_{chunk_index}",
                                                    document_id=document_id,
                                                    page_number=page_num,
                                                    text=sub_slice,
                                                )
                                            )
                                            chunk_index += 1
                                        start = end - chunk_overlap if end < len(sent) else len(sent)
                                    current_chunk = ""

            # Flush leftover text for the page
            if current_chunk.strip():
                chunks.append(
                    Chunk(
                        chunk_id=f"chunk_{chunk_index}",
                        document_id=document_id,
                        page_number=page_num,
                        text=current_chunk.strip(),
                    )
                )
                chunk_index += 1

        return chunks
