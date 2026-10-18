import pytest
import fitz
from fastapi import HTTPException
from app.services.pdf_service import PDFService

def test_extract_text_by_pages():
    # Create an in-memory test PDF
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Hello from test page 1")
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Second page content here")
    pdf_bytes = doc.tobytes()
    doc.close()

    pages, total_chars = PDFService.extract_text_by_pages(pdf_bytes)
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "Hello from test page 1" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "Second page content here" in pages[1]["text"]
    assert total_chars > 0

def test_empty_pdf_raises_400():
    # Empty PDF with no text
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    with pytest.raises(HTTPException) as excinfo:
        PDFService.extract_text_by_pages(pdf_bytes)
    assert excinfo.value.status_code == 400
    assert "no extractable text" in excinfo.value.detail.lower()

def test_invalid_pdf_bytes_raises_400():
    with pytest.raises(HTTPException) as excinfo:
        PDFService.extract_text_by_pages(b"Not a real pdf")
    assert excinfo.value.status_code == 400
