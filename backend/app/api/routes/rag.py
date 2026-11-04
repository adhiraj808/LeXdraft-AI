"""API routes for managing the RAG knowledge base."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


class DocumentAdd(BaseModel):
    # Bounded: each document is embedded in memory and written to the vector store.
    text: str = Field(min_length=50, max_length=50_000)
    case_type: str = Field(min_length=2, max_length=100)
    topic: str = Field(default="", max_length=300)


@router.post("/add-document")
async def add_document(
    payload: DocumentAdd,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Add a legal judgement or document to the RAG knowledge base."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can add documents to the knowledge base",
        )
    nlp = getattr(request.app.state, "nlp_pipeline", None)
    if nlp is None:
        raise HTTPException(
            status_code=503, detail="AI pipeline is not initialised yet"
        )

    doc_id = f"user_{current_user.id[:8]}_{str(uuid.uuid4())[:8]}"
    # Embedding the text is CPU-bound (and the first call loads the model): keep it off the event loop.
    added = await asyncio.to_thread(
        nlp.add_legal_document,
        doc_id=doc_id,
        text=payload.text,
        case_type=payload.case_type,
        topic=payload.topic,
    )
    if not added:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG is not available (optional packages missing or ENABLE_RAG=false). "
            "Install them with: pip install -r requirements-ml.txt",
        )
    return {"message": "Document added to knowledge base", "doc_id": doc_id}


@router.get("/status")
async def rag_status(request: Request, current_user: User = Depends(get_current_user)):
    """Check RAG status and document count (never triggers the lazy model load)."""
    nlp = getattr(request.app.state, "nlp_pipeline", None)
    if nlp is None or nlp.retriever is None:
        return {"status": "inactive", "documents_in_db": 0}
    return nlp.retriever.status()
