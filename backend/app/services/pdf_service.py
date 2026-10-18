import fitz  # PyMuPDF
from fastapi import HTTPException, UploadFile, status
from typing import List, Dict, Any, Tuple
from ..config import settings

class PDFService:
    @staticmethod
    async def validate_and_read(file: UploadFile) -> bytes:
        """
        Validates file extension, MIME type, size limit, and PDF magic bytes.
        Returns file content bytes.
        """
        # Validate file extension
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format: '{filename}'. Only PDF files are supported.",
            )

        # Read file bytes
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        # Validate file size
        if len(content) > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB.",
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
        Extracts text from PDF bytes page by page.
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

        if doc.is_encrypted:
            doc.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is password-protected or encrypted. Please upload an unencrypted PDF.",
            )

        pages = []
        total_chars = 0

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            # 1-based page numbering
            page_num = page_idx + 1
            pages.append({"page_number": page_num, "text": page_text})
            total_chars += len(page_text)

        doc.close()

        if total_chars == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "PDF contains no extractable text. Scanned or image-only PDFs "
                    "are not supported in this version."
                ),
            )

        return pages, total_chars
