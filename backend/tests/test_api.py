import io
import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from app.api.routes import (
    health_check,
    extract_document,
    upload_document,
    list_documents,
    get_document_summary,
    ask_document_question,
    delete_document,
    document_store,
)
from app.schemas.document import AskRequest, ChatMessage


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
    res = health_check()
    assert res.status == "healthy"
    assert res.version == "0.1.0"


def test_extract_endpoint_valid():
    pdf_bytes = create_sample_pdf()
    file = UploadFile(
        file=io.BytesIO(pdf_bytes),
        filename="sample.pdf",
    )
    res = extract_document(file=file)
    assert res.filename == "sample.pdf"
    assert res.page_count == 2
    assert len(res.pages) == 2
    assert res.pages[0].page_number == 1
    assert "Antigravity" in res.pages[0].text


def test_extract_invalid_extension():
    file = UploadFile(
        file=io.BytesIO(b"hello world"),
        filename="sample.txt",
    )
    with pytest.raises(HTTPException) as exc:
        extract_document(file=file)
    assert exc.value.status_code == 400
    assert "Only PDF files are supported" in exc.value.detail


def test_upload_and_delete_document():
    pdf_bytes = create_sample_pdf()
    file = UploadFile(
        file=io.BytesIO(pdf_bytes),
        filename="test_doc.pdf",
    )
    res = upload_document(file=file)
    assert res.filename == "test_doc.pdf"
    assert res.page_count == 2
    assert res.chunk_count > 0
    assert res.status == "ready"
    doc_id = res.document_id

    # Verify present in store
    assert document_store.get(doc_id) is not None

    # Delete
    del_res = delete_document(doc_id)
    assert del_res.status == "deleted"
    assert del_res.document_id == doc_id

    # Verify 404 after deletion
    with pytest.raises(HTTPException) as exc:
        get_document_summary(doc_id)
    assert exc.value.status_code == 404


def test_ask_request_validation():
    # Valid question
    req = AskRequest(question="What is SolarPulse?")
    assert req.question == "What is SolarPulse?"

    # Trimming whitespace
    req_trimmed = AskRequest(question="   What is this?   ")
    assert req_trimmed.question == "What is this?"

    # Whitespace only should fail
    with pytest.raises(ValidationError):
        AskRequest(question="     ")

    # Too short
    with pytest.raises(ValidationError):
        AskRequest(question="a")


def test_list_documents_and_sqlite_persistence():
    pdf_bytes = create_sample_pdf()
    file = UploadFile(
        file=io.BytesIO(pdf_bytes),
        filename="persistent_doc.pdf",
    )
    res = upload_document(file=file)
    doc_id = res.document_id

    # Test listing documents from SQLite
    docs = list_documents()
    assert any(d.document_id == doc_id for d in docs)

    # Test clearing memory cache to verify SQLite rehydration
    document_store._store.clear()
    rehydrated = document_store.get(doc_id)
    assert rehydrated is not None
    assert rehydrated["filename"] == "persistent_doc.pdf"
    assert len(rehydrated["pages"]) == 2
    assert rehydrated["index"] is not None

    # Test chat history validation
    history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi, how can I help?"),
    ]
    req = AskRequest(question="What is this document about?", history=history)
    assert len(req.history) == 2

    # Clean up
    delete_document(doc_id)

