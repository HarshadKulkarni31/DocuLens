import uuid
import json
import logging
import threading
from collections import OrderedDict
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from ..schemas.document import (
    HealthResponse,
    DocumentExtractResponse,
    DocumentUploadResponse,
    DocumentListItem,
    SummaryResponse,
    AskRequest,
    AskResponse,
    DeleteResponse,
    PageExtract,
)
from ..services.pdf_service import PDFService
from ..services.chunking_service import ChunkingService, Chunk
from ..services.retrieval_service import DocumentIndex
from ..services.gemini_service import GeminiService
from ..db.database import DatabaseService
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Document Intelligence"])


class DocumentStore:
    """
    Hybrid in-memory LRU cache backed by SQLite persistent storage.
    Documents survive server restarts and rehydrate vector indexes in milliseconds.
    """

    def __init__(self, db_service: DatabaseService, max_capacity: int = 50):
        self._lock = threading.Lock()
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.db = db_service
        self.max_capacity = max_capacity

    def get(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            # 1. Check memory cache first
            if document_id in self._store:
                self._store.move_to_end(document_id)
                return self._store[document_id]

        # 2. Check persistent SQLite database
        persisted = self.db.get_document(document_id)
        if not persisted:
            return None

        # 3. Rehydrate into memory with precomputed embeddings
        chunks = [
            Chunk(
                chunk_id=c["chunk_id"],
                document_id=document_id,
                page_number=c["page_number"],
                text=c["text"],
            )
            for c in persisted["raw_chunks"]
        ]

        try:
            index = DocumentIndex(
                document_id=document_id,
                chunks=chunks,
                precomputed_embeddings=persisted["embeddings"],
            )
        except Exception as e:
            logger.error(f"Failed to rehydrate index for {document_id}: {e}")
            return None

        doc_data = {
            "document_id": document_id,
            "filename": persisted["filename"],
            "file_size": persisted["file_size"],
            "page_count": persisted["page_count"],
            "pages": persisted["pages"],
            "chunks": chunks,
            "index": index,
            "summary": persisted["summary"],
            "key_points": persisted["key_points"],
        }

        with self._lock:
            self._store[document_id] = doc_data
            self._store.move_to_end(document_id)
            while len(self._store) > self.max_capacity:
                self._store.popitem(last=False)

        return doc_data

    def set(
        self,
        document_id: str,
        data: Dict[str, Any],
        file_size: int = 0,
    ):
        with self._lock:
            if document_id in self._store:
                self._store.move_to_end(document_id)
            self._store[document_id] = data
            while len(self._store) > self.max_capacity:
                self._store.popitem(last=False)

        # Persist to database
        index: DocumentIndex = data.get("index")
        embeddings = index.embeddings_matrix if index is not None else None
        self.db.save_document(
            document_id=document_id,
            filename=data.get("filename", "document.pdf"),
            file_size=file_size,
            pages=data.get("pages", []),
            chunks=data.get("chunks", []),
            embeddings=embeddings,
        )

    def update_summary(self, document_id: str, summary: str, key_points: List[str]):
        with self._lock:
            if document_id in self._store:
                self._store[document_id]["summary"] = summary
                self._store[document_id]["key_points"] = key_points
        self.db.update_summary(document_id, summary, key_points)

    def delete(self, document_id: str) -> bool:
        with self._lock:
            self._store.pop(document_id, None)
        return self.db.delete_document(document_id)

    def clear(self):
        with self._lock:
            self._store.clear()


# Shared instances
db_service = DatabaseService()
document_store = DocumentStore(db_service=db_service)
pdf_service = PDFService()
chunking_service = ChunkingService()
gemini_service = GeminiService()


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint to verify service availability."""
    return HealthResponse(status="healthy", version=settings.VERSION)


@router.get("/documents", response_model=List[DocumentListItem])
def list_documents():
    """Returns a list of all persistent documents in the library."""
    items = db_service.list_documents()
    return [
        DocumentListItem(
            document_id=item["document_id"],
            filename=item["filename"],
            file_size=item.get("file_size", 0),
            page_count=item["page_count"],
            chunk_count=item["chunk_count"],
            created_at=item.get("created_at"),
            has_summary=bool(item.get("has_summary", False)),
        )
        for item in items
    ]


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
    3. Generates embeddings and builds vector index.
    4. Persists document, chunks, and embeddings to SQLite database.
    5. Registers document in memory for fast Q&A and summary queries.
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

    # Store in persistent hybrid registry
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
        file_size=len(pdf_bytes),
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename or "uploaded.pdf",
        page_count=len(pages),
        chunk_count=len(chunks),
        file_size=len(pdf_bytes),
        status="ready",
    )


@router.post("/documents/{document_id}/summary", response_model=SummaryResponse)
def get_document_summary(document_id: str):
    """
    Generates or retrieves a cached executive summary and key points for a document.
    Caches results persistently in SQLite.
    """
    doc = document_store.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    # Return cached summary if already generated
    if doc.get("summary") is not None:
        return SummaryResponse(
            document_id=document_id,
            summary=doc["summary"],
            key_points=doc["key_points"] or [],
        )

    summary, key_points = gemini_service.generate_summary(doc["pages"])

    # Cache result in memory and database
    document_store.update_summary(document_id, summary, key_points)

    return SummaryResponse(
        document_id=document_id,
        summary=summary,
        key_points=key_points,
    )


@router.post("/documents/{document_id}/ask", response_model=AskResponse)
def ask_document_question(document_id: str, request: AskRequest):
    """
    Context-grounded question answering with multi-turn conversation support:
    1. Embeds question and retrieves top-k relevant chunks from vector index.
    2. Sends context, preceding conversation turns, and question to Gemini.
    3. Maps citations back to true chunk metadata with page numbers and excerpts.
    """
    doc = document_store.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    index: DocumentIndex = doc["index"]
    retrieved_chunks = index.search(request.question, top_k=settings.TOP_K)

    answer, sources = gemini_service.answer_question(
        question=request.question,
        retrieved_chunks=retrieved_chunks,
        history=request.history,
    )

    return AskResponse(answer=answer, sources=sources)


@router.post("/documents/{document_id}/ask/stream")
def ask_document_question_stream(document_id: str, request: AskRequest):
    """
    Real-time streaming question answering using Server-Sent Events (SSE).
    Streams source citations followed by text tokens as generated by Gemini.
    """
    doc = document_store.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    index: DocumentIndex = doc["index"]
    retrieved_chunks = index.search(request.question, top_k=settings.TOP_K)

    def event_generator():
        try:
            for event in gemini_service.stream_answer_question(
                question=request.question,
                retrieved_chunks=retrieved_chunks,
                history=request.history,
            ):
                event_type = event.get("type", "message")
                data_json = json.dumps(event.get("data", {}))
                yield f"event: {event_type}\ndata: {data_json}\n\n"
        except Exception as e:
            logger.error(f"Error in SSE streaming: {e}")
            err_json = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {err_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
def delete_document(document_id: str):
    """Removes a document and its index from persistent storage and memory."""
    if document_store.delete(document_id):
        return DeleteResponse(
            status="deleted",
            document_id=document_id,
            message=f"Document '{document_id}' successfully removed.",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Document '{document_id}' not found.",
    )
