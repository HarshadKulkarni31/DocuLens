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


def test_extract_csv_structured_data():
    csv_content = b"id,name,role,salary\n1,Alice,Engineer,120000\n2,Bob,Product Manager,135000\n"
    pages, total_chars = PDFService.extract_document(csv_content, filename="employees.csv")
    assert len(pages) == 1
    assert "Alice" in pages[0]["text"]
    assert "Product Manager" in pages[0]["text"]
    assert total_chars > 0


def test_extract_json_structured_data():
    json_content = b'[{"project": "DocuLens", "type": "RAG", "stars": 500}]'
    pages, total_chars = PDFService.extract_document(json_content, filename="data.json")
    assert len(pages) == 1
    assert "DocuLens" in pages[0]["text"]
    assert total_chars > 0


def test_extract_plain_text():
    text_content = b"This is a plain text document.\n\nIt contains multiple paragraphs for RAG retrieval."
    pages, total_chars = PDFService.extract_document(text_content, filename="notes.txt")
    assert len(pages) == 1
    assert "plain text document" in pages[0]["text"]
    assert total_chars > 0


