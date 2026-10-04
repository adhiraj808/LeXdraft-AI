"""Pydantic schemas for case endpoints."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, List


class CaseSubmit(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    jurisdiction: Optional[str] = None
    petitioner_name: Optional[str] = None
    respondent_name: Optional[str] = None
    incident_date: Optional[str] = None
    case_description: str = Field(..., min_length=50)
    sections_alleged: Optional[str] = None
    relief_sought: Optional[str] = None


class ExtractedEntities(BaseModel):
    persons: List[str] = []
    organizations: List[str] = []
    dates: List[str] = []
    statutes: List[str] = []
    locations: List[str] = []
    money: List[str] = []
    courts: List[str] = []


class DraftSections(BaseModel):
    title_block: str = ""
    complaint_body: str = ""
    prayer: str = ""
    list_of_witnesses: str = ""
    list_of_documents: str = ""
    affidavit: str = ""
    evidence_affidavit: str = ""


class DraftResponse(BaseModel):
    id: str
    case_id: str
    sections: DraftSections
    full_text: Optional[str]
    version: int
    model_used: Optional[str]
    generation_time_seconds: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseResponse(BaseModel):
    id: str
    title: str
    jurisdiction: Optional[str]
    petitioner_name: Optional[str]
    respondent_name: Optional[str]
    incident_date: Optional[str]
    case_description: str
    sections_alleged: Optional[str]
    relief_sought: Optional[str]
    case_type: Optional[str]
    case_type_confidence: Optional[float]
    extracted_entities: Optional[Dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime
    draft: Optional[DraftResponse] = None

    class Config:
        from_attributes = True


class CaseListItem(BaseModel):
    id: str
    title: str
    case_type: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RegenerateRequest(BaseModel):
    section: str = Field(
        ...,
        description=(
            "Section to regenerate: title_block|complaint_body|prayer|"
            "list_of_witnesses|list_of_documents|affidavit|evidence_affidavit|all"
        ),
    )
    additional_context: Optional[str] = None


class PromptSubmit(BaseModel):
    prompt: str = Field(..., min_length=30, max_length=6000, description="Free-form case narrative")
