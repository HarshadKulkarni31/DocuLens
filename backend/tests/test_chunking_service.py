import pytest
from app.services.chunking_service import ChunkingService

def test_chunking_preserves_page_metadata():
    pages = [
        {"page_number": 1, "text": "Page one paragraph text. " * 30},
        {"page_number": 2, "text": "Page two text with important facts. " * 30},
    ]
    chunks = ChunkingService.chunk_document(
        document_id="test_doc",
        pages=pages,
        chunk_size=300,
        chunk_overlap=50,
    )
    assert len(chunks) > 0
    # Every chunk must have a 1-based page number and non-empty text
    for c in chunks:
        assert c.page_number in [1, 2]
        assert len(c.text.strip()) > 0
        assert c.chunk_id.startswith("chunk_")
        assert c.document_id == "test_doc"

def test_chunking_skips_empty_pages():
    pages = [
        {"page_number": 1, "text": "   "},
        {"page_number": 2, "text": "Hello world from page 2"},
    ]
    chunks = ChunkingService.chunk_document(
        document_id="test_doc",
        pages=pages,
    )
    assert len(chunks) == 1
    assert chunks[0].page_number == 2
    assert "Hello world from page 2" in chunks[0].text

