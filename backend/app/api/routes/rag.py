"""API routes for managing the RAG knowledge base."""

from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.core.security import get_current_user
from app.models.user import User
import uuid

router = APIRouter()


class DocumentAdd(BaseModel):
    text: str
    case_type: str
    topic: Optional[str] = ""


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
    nlp = request.app.state.nlp_pipeline
    doc_id = f"user_{current_user.id[:8]}_{str(uuid.uuid4())[:8]}"
    nlp.add_legal_document(
        doc_id=doc_id,
        text=payload.text,
        case_type=payload.case_type,
        topic=payload.topic,
    )
    return {"message": "Document added to knowledge base", "doc_id": doc_id}


@router.get("/status")
async def rag_status(request: Request, current_user: User = Depends(get_current_user)):
    """Check RAG status and document count."""
    nlp = request.app.state.nlp_pipeline
    if nlp.retriever and nlp.retriever._loaded:
        count = nlp.retriever.collection.count()
        return {"status": "active", "documents_in_db": count}
    return {"status": "inactive", "documents_in_db": 0}
