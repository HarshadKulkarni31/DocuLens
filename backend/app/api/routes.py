import uuid
import logging
import threading
from collections import OrderedDict
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from ..schemas.document import (
    HealthResponse,
    DocumentExtractResponse,
    DocumentUploadResponse,
    SummaryResponse,
    AskRequest,
    AskResponse,
    DeleteResponse,
    PageExtract,
)
from ..services.pdf_service import PDFService
from ..services.chunking_service import ChunkingService
from ..services.retrieval_service import DocumentIndex
from ..services.gemini_service import GeminiService
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Document Intelligence"])


class DocumentStore:
    """Thread-safe in-memory LRU document storage for session management."""

    def __init__(self, max_capacity: int = 50):
        self._lock = threading.Lock()
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_capacity = max_capacity

    def get(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if document_id in self._store:
                self._store.move_to_end(document_id)
                return self._store[document_id]
            return None

    def set(self, document_id: str, data: Dict[str, Any]):
        with self._lock:
            if document_id in self._store:
                self._store.move_to_end(document_id)
            self._store[document_id] = data
            while len(self._store) > self.max_capacity:
                evicted_id, _ = self._store.popitem(last=False)
                logger.info(f"Evicted old document '{evicted_id}' from memory store.")

    def delete(self, document_id: str) -> bool:
        with self._lock:
            return bool(self._store.pop(document_id, None))

    def clear(self):
        with self._lock:
            self._store.clear()


# Shared instances
document_store = DocumentStore()
pdf_service = PDFService()
chunking_service = ChunkingService()
gemini_service = GeminiService()


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint to verify service availability."""
    return HealthResponse(status="healthy", version=settings.VERSION)


@router.post("/documents/extract", response_model=DocumentExtractResponse)
def extract_document(file: UploadFile = File(...)):
    """
    Validates and extracts raw text page by page from an uploaded PDF.
    Does not index or store the document.
    """
    pdf_bytes = pdf_service.validate_and_read(file)
    pages, total_chars = pdf_service.extract_text_by_pages(pdf_bytes)

    page_extracts = [
        PageExtract(page_number=p["page_number"], text=p["text"]) for p in pages
    ]

    return DocumentExtractResponse(
        filename=file.filename or "unknown.pdf",
        page_count=len(pages),
        character_count=total_chars,
        pages=page_extracts,
    )


@router.post("/documents", response_model=DocumentUploadResponse)
def upload_document(file: UploadFile = File(...)):
    """
    Full document ingestion pipeline:
    1. Validates and extracts page-numbered text from PDF.
    2. Chunks text with preserved page metadata.
    3. Generates embeddings and builds in-memory vector index (FAISS).
    4. Registers document for subsequent Q&A and summary queries.
    """
    pdf_bytes = pdf_service.validate_and_read(file)
    pages, total_chars = pdf_service.extract_text_by_pages(pdf_bytes)

    doc_id = str(uuid.uuid4())

    # Create overlapping chunks
    chunks = chunking_service.chunk_document(document_id=doc_id, pages=pages)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not generate valid text chunks from document.",
        )

    # Build vector index
    try:
        index = DocumentIndex(document_id=doc_id, chunks=chunks)
    except Exception as e:
        logger.error(f"Failed to build index: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build vector index: {str(e)}",
        )

    # Store in thread-safe memory registry
    document_store.set(
        doc_id,
        {
            "filename": file.filename or "uploaded.pdf",
            "page_count": len(pages),
            "pages": pages,
            "chunks": chunks,
            "index": index,
            "summary": None,
            "key_points": None,
        },
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename or "uploaded.pdf",
        page_count=len(pages),
        chunk_count=len(chunks),
        status="ready",
    )


@router.post("/documents/{document_id}/summary", response_model=SummaryResponse)
def get_document_summary(document_id: str):
    """
    Generates or retrieves a cached executive summary and key points for a document.
    """
    doc = document_store.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found. Please upload the PDF again.",
        )

    # Return cached summary if already generated
    if doc.get("summary") is not None:
        return SummaryResponse(
            document_id=document_id,
            summary=doc["summary"],
            key_points=doc["key_points"] or [],
        )

    summary, key_points = gemini_service.generate_summary(doc["pages"])

    # Cache result
    doc["summary"] = summary
    doc["key_points"] = key_points

    return SummaryResponse(
        document_id=document_id,
        summary=summary,
        key_points=key_points,
    )


@router.post("/documents/{document_id}/ask", response_model=AskResponse)
def ask_document_question(document_id: str, request: AskRequest):
    """
    Context-grounded question answering:
    1. Embeds question and retrieves top-k relevant chunks from FAISS index.
    2. Sends context and question to Gemini with strict grounding instructions.
    3. Maps citations back to true chunk metadata with page numbers and excerpts.
    """
    doc = document_store.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found. Please upload the PDF again.",
        )

    index: DocumentIndex = doc["index"]
    retrieved_chunks = index.search(request.question, top_k=settings.TOP_K)

    answer, sources = gemini_service.answer_question(
        question=request.question,
        retrieved_chunks=retrieved_chunks,
    )

    return AskResponse(answer=answer, sources=sources)


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
def delete_document(document_id: str):
    """Removes a document and its index from memory."""
    if document_store.delete(document_id):
        return DeleteResponse(
            status="deleted",
            document_id=document_id,
            message=f"Document '{document_id}' successfully removed from memory.",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Document '{document_id}' not found.",
    )
