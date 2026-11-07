"""Pydantic schemas for case endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Order in which sections are generated, stored and exported.
SECTION_NAMES = (
    "title_block",
    "complaint_body",
    "prayer",
    "list_of_witnesses",
    "list_of_documents",
    "affidavit",
    "evidence_affidavit",
)

# Upper bounds mirror the database column sizes (see app/models/case.py). Without
# them an over-long value is only rejected by PostgreSQL, as an opaque HTTP 500.
MAX_DESCRIPTION_CHARS = 20_000
MAX_RELIEF_CHARS = 5_000
MAX_CONTEXT_CHARS = 2_000


class CaseSubmit(BaseModel):
    # Strip first, then apply the length limits (30 spaces must not count as a description).
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=5, max_length=500)
    jurisdiction: Optional[str] = Field(default=None, max_length=200)
    petitioner_name: Optional[str] = Field(default=None, max_length=300)
    respondent_name: Optional[str] = Field(default=None, max_length=300)
    incident_date: Optional[str] = Field(default=None, max_length=50)
    case_description: str = Field(..., min_length=30, max_length=MAX_DESCRIPTION_CHARS)
    sections_alleged: Optional[str] = Field(default=None, max_length=500)
    relief_sought: Optional[str] = Field(default=None, max_length=MAX_RELIEF_CHARS)

    @field_validator(
        "jurisdiction",
        "petitioner_name",
        "respondent_name",
        "incident_date",
        "sections_alleged",
        "relief_sought",
    )
    @classmethod
    def blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        value = (value or "").strip()
        return value or None


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
    # Phase 1
    raw_prompt: Optional[str] = None
    fact_sheet: Optional[Dict[str, Any]] = None
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
    section: Literal[
        "title_block",
        "complaint_body",
        "prayer",
        "list_of_witnesses",
        "list_of_documents",
        "affidavit",
        "evidence_affidavit",
        "all",
    ] = Field(..., description="Section to regenerate, or 'all' for the whole draft")
    additional_context: Optional[str] = Field(
        default=None, max_length=MAX_CONTEXT_CHARS
    )


class PromptSubmit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(
        ..., min_length=30, max_length=6000, description="Free-form case narrative"
    )
