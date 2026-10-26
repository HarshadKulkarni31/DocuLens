import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Directory for SQLite database
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "doculens.db"


def get_db_connection() -> sqlite3.Connection:
    """Creates a connection to SQLite database with foreign keys enabled."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initializes tables for persistent document and chunk storage."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    page_count INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    summary TEXT,
                    key_points_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding_bytes BLOB,
                    FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE
                );
            """)
            
            # Indexes for quick retrieval
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_doc ON pages(document_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);")
        logger.info(f"Initialized persistent database at {DB_PATH}")
    finally:
        conn.close()


class DatabaseService:
    """Handles CRUD operations for persistent documents, pages, and chunks."""

    def __init__(self):
        init_db()

    def save_document(
        self,
        document_id: str,
        filename: str,
        file_size: int,
        pages: List[Dict[str, Any]],
        chunks: List[Any],
        embeddings: Optional[np.ndarray] = None,
    ):
        """Persists a new document, its page extracts, and its vector chunks."""
        conn = get_db_connection()
        try:
            with conn:
                # Insert document record
                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents 
                    (document_id, filename, file_size, page_count, chunk_count)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (document_id, filename, file_size, len(pages), len(chunks)),
                )

                # Delete existing pages/chunks if replacing
                conn.execute("DELETE FROM pages WHERE document_id = ?", (document_id,))
                conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

                # Insert pages
                conn.executemany(
                    """
                    INSERT INTO pages (document_id, page_number, text)
                    VALUES (?, ?, ?)
                    """,
                    [(document_id, p["page_number"], p["text"]) for p in pages],
                )

                # Insert chunks with embedding bytes
                chunk_rows = []
                for idx, chunk in enumerate(chunks):
                    emb_bytes = None
                    if embeddings is not None and idx < len(embeddings):
                        emb_bytes = embeddings[idx].astype(np.float32).tobytes()
                    chunk_rows.append((
                        chunk.chunk_id,
                        document_id,
                        chunk.page_number,
                        idx,
                        chunk.text,
                        emb_bytes,
                    ))

                conn.executemany(
                    """
                    INSERT INTO chunks 
                    (chunk_id, document_id, page_number, chunk_index, text, embedding_bytes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    chunk_rows,
                )
            logger.info(f"Persisted document '{document_id}' ({filename}) to SQLite database.")
        finally:
            conn.close()

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves document metadata, pages, chunks, and cached embeddings from SQLite."""
        conn = get_db_connection()
        try:
            doc_row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
            if not doc_row:
                return None

            page_rows = conn.execute(
                "SELECT page_number, text FROM pages WHERE document_id = ? ORDER BY page_number ASC",
                (document_id,),
            ).fetchall()

            chunk_rows = conn.execute(
                "SELECT chunk_id, page_number, chunk_index, text, embedding_bytes FROM chunks WHERE document_id = ? ORDER BY chunk_index ASC",
                (document_id,),
            ).fetchall()

            key_points = []
            if doc_row["key_points_json"]:
                try:
                    key_points = json.loads(doc_row["key_points_json"])
                except Exception:
                    key_points = []

            # Reconstruct embeddings array if present
            embeddings_list = []
            for r in chunk_rows:
                if r["embedding_bytes"]:
                    emb = np.frombuffer(r["embedding_bytes"], dtype=np.float32)
                    embeddings_list.append(emb)

            embeddings = np.array(embeddings_list) if len(embeddings_list) == len(chunk_rows) and len(chunk_rows) > 0 else None

            return {
                "document_id": doc_row["document_id"],
                "filename": doc_row["filename"],
                "file_size": doc_row["file_size"],
                "page_count": doc_row["page_count"],
                "chunk_count": doc_row["chunk_count"],
                "summary": doc_row["summary"],
                "key_points": key_points,
                "created_at": doc_row["created_at"],
                "pages": [{"page_number": p["page_number"], "text": p["text"]} for p in page_rows],
                "raw_chunks": [
                    {
                        "chunk_id": c["chunk_id"],
                        "page_number": c["page_number"],
                        "chunk_index": c["chunk_index"],
                        "text": c["text"],
                    }
                    for c in chunk_rows
                ],
                "embeddings": embeddings,
            }
        finally:
            conn.close()

    def list_documents(self) -> List[Dict[str, Any]]:
        """Lists all stored documents ordered by creation time descending."""
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT document_id, filename, file_size, page_count, chunk_count, created_at,
                       (summary IS NOT NULL) AS has_summary
                FROM documents 
                ORDER BY created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_summary(self, document_id: str, summary: str, key_points: List[str]):
        """Caches summary and key findings in database."""
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE documents 
                    SET summary = ?, key_points_json = ? 
                    WHERE document_id = ?
                    """,
                    (summary, json.dumps(key_points), document_id),
                )
        finally:
            conn.close()

    def delete_document(self, document_id: str) -> bool:
        """Deletes a document and its associated pages and chunks from SQLite."""
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()
