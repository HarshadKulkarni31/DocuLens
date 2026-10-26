from typing import List, Dict, Any, Tuple
from fastapi import HTTPException, UploadFile, status

# Import modern pymupdf without deprecation warnings
try:
    import pymupdf as fitz
except ImportError:
    import fitz

from ..config import settings


class PDFService:
    @staticmethod
    def validate_and_read(file: UploadFile) -> bytes:
        """
        Validates file extension, size limit, and PDF magic bytes.
        Reads file in 1MB chunks to enforce size limit safely without memory exhaustion.
        Returns validated file bytes.
        """
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format: '{filename}'. Only PDF files are supported.",
            )

        raw_file = getattr(file, "file", file)
        chunk_size = 1024 * 1024  # 1MB
        chunks: List[bytes] = []
        total_size = 0

        while True:
            chunk = raw_file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > settings.MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB.",
                )
            chunks.append(chunk)

        content = b"".join(chunks)

        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        # Validate PDF signature (magic bytes)
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF signature. The file does not appear to be a valid PDF document.",
            )

        return content

    @staticmethod
    def extract_text_by_pages(pdf_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
        """
        Extracts text from PDF bytes page by page using a safe context manager.
        Returns (pages_list, total_character_count).
        Handles encrypted, corrupted, and image-only/scanned PDFs.
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse PDF document: {str(e)}",
            )

        with doc:
            if doc.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Document is password-protected or encrypted. Please upload an unencrypted PDF.",
                )

            pages: List[Dict[str, Any]] = []
            total_chars = 0

            for page_idx in range(len(doc)):
                try:
                    page = doc[page_idx]
                    page_text = page.get_text("text").strip()
                except Exception:
                    page_text = ""

                # 1-based page numbering
                page_num = page_idx + 1
                pages.append({"page_number": page_num, "text": page_text})
                total_chars += len(page_text)

        if total_chars == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "PDF contains no extractable text. Scanned or image-only PDFs "
                    "are not supported in this version."
                ),
            )

        return pages, total_chars
