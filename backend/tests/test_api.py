import io
import fitz
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_sample_pdf() -> bytes:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Antigravity is an AI pair programmer. It builds high quality applications.")
    page2 = doc.new_page()
    page2.insert_text((50, 72), "DocuLens uses FastAPI, PyMuPDF, FAISS and Google Gemini.")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_extract_endpoint():
    pdf_bytes = create_sample_pdf()
    response = client.post(
        "/api/documents/extract",
        files={"file": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "sample.pdf"
    assert data["page_count"] == 2
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page_number"] == 1

def test_extract_invalid_extension():
    response = client.post(
        "/api/documents/extract",
        files={"file": ("sample.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]

def test_upload_and_delete_document():
    pdf_bytes = create_sample_pdf()
    response = client.post(
        "/api/documents",
        files={"file": ("test_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    doc_id = data["document_id"]
    assert data["page_count"] == 2
    assert data["chunk_count"] > 0
    assert data["status"] == "ready"

    # Test delete
    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Test 404 after delete
    get_res = client.post(f"/api/documents/{doc_id}/summary")
    assert get_res.status_code == 404

