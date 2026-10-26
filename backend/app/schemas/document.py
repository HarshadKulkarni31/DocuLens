from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"


class PageExtract(BaseModel):
    page_number: int = Field(..., description="1-based page number")
    text: str = Field(..., description="Extracted text from page")


class DocumentExtractResponse(BaseModel):
    filename: str
    page_count: int
    character_count: int
    pages: List[PageExtract]


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    file_size: Optional[int] = 0
    status: str = "ready"


class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    file_size: int
    page_count: int
    chunk_count: int
    created_at: Optional[str] = None
    has_summary: bool = False


class SummaryResponse(BaseModel):
    document_id: str
    summary: str
    key_points: List[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., max_length=2000, description="Message content")


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Question about the document",
    )
    history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="Optional preceding conversation turns for contextual follow-up questions",
    )

    @field_validator("question")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Question must contain at least 2 non-whitespace characters.")
        return trimmed


class SourceChunk(BaseModel):
    chunk_id: str
    page_number: int
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceChunk] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    status: str = "deleted"
    document_id: str
    message: str
