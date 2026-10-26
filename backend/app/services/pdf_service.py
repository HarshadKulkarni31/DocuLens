import io
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from fastapi import HTTPException, UploadFile, status

# Import modern pymupdf without deprecation warnings
try:
    import pymupdf as fitz
except ImportError:
    import fitz

from ..config import settings

logger = logging.getLogger(__name__)


class PDFService:
    """
    Unified ingestion service for multi-format documents and datasets:
    - Unstructured: PDF documents, plain text (.txt), Markdown (.md)
    - Structured: CSV spreadsheets (.csv), TSV (.tsv), JSON records (.json)
    - Scanned PDFs: Multimodal OCR via Gemini Vision fallback
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".tsv", ".json", ".txt", ".md"}

    @classmethod
    def validate_and_read(cls, file: UploadFile) -> bytes:
        """
        Validates file extension, size limit, and PDF signature.
        Reads file in 1MB chunks to enforce size limit safely without memory exhaustion.
        Returns validated file bytes.
        """
        filename = file.filename or ""
        ext = Path(filename).suffix.lower()

        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: '{filename}'. Supported formats: PDF, CSV, TSV, JSON, TXT, MD.",
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

        # Validate PDF signature (magic bytes) if extension is .pdf
        if ext == ".pdf" and not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF signature. The file does not appear to be a valid PDF document.",
            )

        return content

    @classmethod
    def extract_document(cls, file_bytes: bytes, filename: str = "document.pdf") -> Tuple[List[Dict[str, Any]], int]:
        """
        Dispatches file extraction based on file extension.
        Returns (pages_list, total_character_count).
        """
        ext = Path(filename).suffix.lower()

        if ext == ".csv":
            return cls.extract_csv(file_bytes, delimiter=",")
        elif ext == ".tsv":
            return cls.extract_csv(file_bytes, delimiter="\t")
        elif ext == ".json":
            return cls.extract_json(file_bytes)
        elif ext in (".txt", ".md"):
            return cls.extract_text(file_bytes)
        else:
            return cls.extract_text_by_pages(file_bytes)

    @classmethod
    def extract_text_by_pages(cls, pdf_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
        """
        Extracts text from PDF bytes page by page using PyMuPDF.
        If no text is found (scanned document), attempts OCR via Gemini Vision.
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

                page_num = page_idx + 1
                pages.append({"page_number": page_num, "text": page_text})
                total_chars += len(page_text)

        # Scanned PDF OCR Fallback: If 0 selectable text characters
        if total_chars == 0 and len(pages) > 0:
            pages, total_chars = cls._attempt_scanned_ocr(pdf_bytes, len(pages))

        if total_chars == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "PDF contains no extractable text. Scanned or image-only PDFs "
                    "with no detectable text are not supported."
                ),
            )

        return pages, total_chars

    @classmethod
    def _attempt_scanned_ocr(cls, pdf_bytes: bytes, num_pages: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        Extracts text from scanned image pages using PyMuPDF pixmaps and Gemini Vision.
        """
        if not settings.GEMINI_API_KEY or "replace_with" in settings.GEMINI_API_KEY:
            return [], 0

        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            ocr_pages = []
            total_chars = 0

            # Process up to 10 pages for scanned documents to avoid latency/timeouts
            max_ocr_pages = min(num_pages, 10)
            with doc:
                for idx in range(max_ocr_pages):
                    page = doc[idx]
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")

                    prompt = "Extract all text, numbers, headings, tables, and content from this document page accurately. Preserve layout where possible."
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=[
                            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                            prompt,
                        ],
                    )
                    extracted = (response.text or "").strip()
                    ocr_pages.append({"page_number": idx + 1, "text": extracted})
                    total_chars += len(extracted)

            return ocr_pages, total_chars
        except Exception as e:
            logger.warning(f"Scanned OCR fallback failed: {e}")
            return [], 0

    @staticmethod
    def extract_csv(csv_bytes: bytes, delimiter: str = ",") -> Tuple[List[Dict[str, Any]], int]:
        """
        Extracts structured records from CSV/TSV spreadsheets into logical page blocks.
        """
        try:
            text_data = csv_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_data = csv_bytes.decode("latin-1")

        lines = [line for line in text_data.splitlines() if line.strip()]
        if not lines:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded spreadsheet is empty.")

        reader = csv.reader(io.StringIO(text_data), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Spreadsheet contains no records.")

        header = rows[0]
        data_rows = rows[1:]

        # Group rows into logical pages (25 records per page)
        rows_per_page = 25
        pages = []
        total_chars = 0
        header_str = ", ".join(header)

        for i in range(0, max(1, len(data_rows)), rows_per_page):
            batch = data_rows[i : i + rows_per_page]
            page_lines = [f"Table Headers: {header_str}\n"]
            for row_idx, row in enumerate(batch, start=i + 1):
                record_items = []
                for col_idx, val in enumerate(row):
                    col_name = header[col_idx] if col_idx < len(header) else f"Column_{col_idx+1}"
                    record_items.append(f"{col_name}: {val.strip()}")
                page_lines.append(f"Record {row_idx}: " + "; ".join(record_items))

            page_text = "\n".join(page_lines).strip()
            page_num = (i // rows_per_page) + 1
            pages.append({"page_number": page_num, "text": page_text})
            total_chars += len(page_text)

        return pages, total_chars

    @staticmethod
    def extract_json(json_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
        """
        Extracts structured JSON objects/arrays into clean searchable pages.
        """
        try:
            text_data = json_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_data = json_bytes.decode("latin-1")

        try:
            data = json.loads(text_data)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON format: {str(e)}")

        pages = []
        total_chars = 0

        if isinstance(data, list):
            items_per_page = 20
            for i in range(0, max(1, len(data)), items_per_page):
                batch = data[i : i + items_per_page]
                page_lines = []
                for idx, item in enumerate(batch, start=i + 1):
                    item_str = json.dumps(item, indent=2) if isinstance(item, (dict, list)) else str(item)
                    page_lines.append(f"Record {idx}:\n{item_str}")
                page_text = "\n\n".join(page_lines).strip()
                page_num = (i // items_per_page) + 1
                pages.append({"page_number": page_num, "text": page_text})
                total_chars += len(page_text)
        elif isinstance(data, dict):
            sections = []
            for k, v in data.items():
                val_str = json.dumps(v, indent=2) if isinstance(v, (dict, list)) else str(v)
                sections.append(f"Section [{k}]:\n{val_str}")

            current_page_text = ""
            page_num = 1
            for sec in sections:
                if len(current_page_text) + len(sec) > 3000 and current_page_text:
                    pages.append({"page_number": page_num, "text": current_page_text.strip()})
                    total_chars += len(current_page_text)
                    page_num += 1
                    current_page_text = sec + "\n\n"
                else:
                    current_page_text += sec + "\n\n"
            if current_page_text.strip():
                pages.append({"page_number": page_num, "text": current_page_text.strip()})
                total_chars += len(current_page_text)
        else:
            pages = [{"page_number": 1, "text": str(data)}]
            total_chars = len(str(data))

        return pages, total_chars

    @staticmethod
    def extract_text(text_bytes: bytes) -> Tuple[List[Dict[str, Any]], int]:
        """
        Extracts plain text or Markdown files, splitting into logical ~3,000 character pages.
        """
        try:
            content = text_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = text_bytes.decode("latin-1")

        if not content.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded text file is empty.")

        paragraphs = content.split("\n\n")
        pages = []
        current_page = []
        current_len = 0
        page_num = 1
        total_chars = 0

        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > 3000 and current_page:
                page_str = "\n\n".join(current_page).strip()
                pages.append({"page_number": page_num, "text": page_str})
                total_chars += len(page_str)
                page_num += 1
                current_page = [p]
                current_len = p_len
            else:
                current_page.append(p)
                current_len += p_len

        if current_page:
            page_str = "\n\n".join(current_page).strip()
            pages.append({"page_number": page_num, "text": page_str})
            total_chars += len(page_str)

        return pages, total_chars
