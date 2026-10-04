"""Business logic layer for case processing."""

import asyncio
import logging
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.case import Case, Draft
from app.models.user import User
from app.schemas.case import CaseSubmit
from app.db.redis_client import (
    cache_case_data, get_case_data, cache_draft,
    get_draft, update_case_status, delete_case_cache, publish_progress
)

logger = logging.getLogger(__name__)


def _model_name(nlp_pipeline) -> str:
    """Human-readable label for which generator produced a draft."""
    gen = getattr(nlp_pipeline, "generator", None)
    if getattr(gen, "use_groq", False):
        return "groq"
    if getattr(gen, "use_model", False):
        return "local-llm"
    return "template"


class CaseService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_case(self, payload: CaseSubmit, user: User) -> Case:
        """Create a new case record and cache the input in Redis."""
        case = Case(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title=payload.title,
            jurisdiction=payload.jurisdiction,
            petitioner_name=payload.petitioner_name,
            respondent_name=payload.respondent_name,
            incident_date=payload.incident_date,
            case_description=payload.case_description,
            sections_alleged=payload.sections_alleged,
            relief_sought=payload.relief_sought,
            status="pending",
        )
        self.db.add(case)
        await self.db.flush()

        # Cache input in Redis for fast pipeline access
        await cache_case_data(case.id, {
            "title": payload.title,
            "jurisdiction": payload.jurisdiction or "",
            "petitioner_name": payload.petitioner_name or "",
            "respondent_name": payload.respondent_name or "",
            "incident_date": payload.incident_date or "",
            "case_description": payload.case_description,
            "sections_alleged": payload.sections_alleged or "",
            "relief_sought": payload.relief_sought or "",
            "status": "pending",
        })

        await self.db.commit()
        await self.db.refresh(case)
        return case

    async def create_case_from_prompt(self, prompt: str, user: User) -> Case:
        """Create a case from a free-form prompt using Groq extraction."""
        from app.nlp.extractor import extract_case_fields
        fields = await asyncio.to_thread(extract_case_fields, prompt)
        if fields:
            title = fields.get("title") or (prompt[:60] + "...")
            if len(title) < 5:
                title = (prompt[:60] + "...")
            payload = CaseSubmit(
                title=title,
                jurisdiction=fields.get("jurisdiction") or None,
                petitioner_name=fields.get("petitioner_name") or None,
                respondent_name=fields.get("respondent_name") or None,
                incident_date=fields.get("incident_date") or None,
                case_description=fields.get("case_description") or prompt,
                sections_alleged=fields.get("sections_alleged") or None,
                relief_sought=fields.get("relief_sought") or None,
            )
        else:
            payload = CaseSubmit(
                title=prompt[:57] + "...",
                case_description=prompt,
            )
        return await self.create_case(payload, user)

    async def process_case(self, case_id: str, nlp_pipeline) -> Case:
        """Run the NLP pipeline on a case and persist results."""
        result = await self.db.execute(
            select(Case).where(Case.id == case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        try:
            await update_case_status(case_id, "processing")
            case.status = "processing"
            await self.db.commit()

            await publish_progress(case_id, "preprocessing")

            case_input = {
                "title": case.title,
                "case_description": case.case_description,
                "petitioner_name": case.petitioner_name,
                "respondent_name": case.respondent_name,
                "incident_date": case.incident_date,
                "jurisdiction": case.jurisdiction,
                "relief_sought": case.relief_sought,
            }

            # Run full NLP pipeline
            pipeline_result = await nlp_pipeline.process(case_input)

            await publish_progress(case_id, "saving_results")

            # Persist NLP outputs to PostgreSQL
            classification = pipeline_result["classification"]
            case.case_type = classification["case_type"]
            case.case_type_confidence = classification["confidence"]
            case.extracted_entities = pipeline_result["entities"]
            case.status = "completed"

            draft_sections = pipeline_result["draft_sections"]
            gen_time = draft_sections.pop("_generation_time", None)
            full_text = draft_sections.pop("_full_text", None)

            # Upsert draft
            draft_result = await self.db.execute(
                select(Draft).where(Draft.case_id == case_id)
            )
            existing_draft = draft_result.scalar_one_or_none()

            if existing_draft:
                existing_draft.sections = draft_sections
                existing_draft.full_text = full_text
                existing_draft.version += 1
                existing_draft.generation_time_seconds = gen_time
                existing_draft.model_used = "flan-t5" if nlp_pipeline.generator.use_model else "template"
                draft = existing_draft
            else:
                draft = Draft(
                    case_id=case_id,
                    sections=draft_sections,
                    full_text=full_text,
                    version=1,
                    model_used=_model_name(nlp_pipeline),
                    generation_time_seconds=gen_time,
                )
                self.db.add(draft)

            await self.db.commit()
            await self.db.refresh(case)

            # Cache draft in Redis
            await cache_draft(case_id, {
                "sections": draft_sections,
                "full_text": full_text,
            })
            await update_case_status(case_id, "completed")
            await publish_progress(case_id, "completed")

            return case

        except Exception as e:
            logger.error(f"Pipeline failed for case {case_id}: {e}")
            case.status = "failed"
            await self.db.commit()
            await update_case_status(case_id, "failed")
            await publish_progress(case_id, "failed")
            raise

    async def get_case(self, case_id: str, user: User) -> Optional[Case]:
        result = await self.db.execute(
            select(Case)
            .options(selectinload(Case.draft))
            .where(Case.id == case_id, Case.user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def list_cases(self, user: User, skip: int = 0, limit: int = 20) -> List[Case]:
        result = await self.db.execute(
            select(Case)
            .where(Case.user_id == user.id)
            .order_by(Case.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_case(self, case_id: str, user: User) -> bool:
        result = await self.db.execute(
            select(Case)
            .options(selectinload(Case.draft))
            .where(Case.id == case_id, Case.user_id == user.id)
        )
        case = result.scalar_one_or_none()
        if not case:
            return False
        await self.db.delete(case)
        await self.db.commit()
        await delete_case_cache(case_id)
        return True

    async def regenerate_section(self, case_id: str, section: str, user: User, nlp_pipeline, additional_context: str = None) -> dict:
        """Regenerate a specific section of an existing draft."""
        case = await self.get_case(case_id, user)
        if not case:
            raise ValueError("Case not found")

        if section == "all":
            await self.process_case(case_id, nlp_pipeline)
            regenerated = await self.get_case(case_id, user)
            if not regenerated or not regenerated.draft:
                raise RuntimeError("Draft regeneration did not produce a draft")
            return {
                "section": "all",
                "sections": regenerated.draft.sections,
                "full_text": regenerated.draft.full_text,
                "version": regenerated.draft.version,
            }

        case_input = {
            "case_description": case.case_description,
            "petitioner_name": case.petitioner_name,
            "respondent_name": case.respondent_name,
            "incident_date": case.incident_date,
            "jurisdiction": case.jurisdiction,
            "relief_sought": case.relief_sought,
        }

        new_content = await nlp_pipeline.regenerate_section(
            section=section,
            case_input=case_input,
            entities=case.extracted_entities or {},
            classification={"case_type": case.case_type or "Civil"},
            additional_context=additional_context,
        )

        # Update draft
        if case.draft:
            sections = dict(case.draft.sections)
            sections[section] = new_content
            case.draft.sections = sections
            case.draft.version += 1
            await self.db.commit()

            # Update cache
            cached = await get_draft(case_id) or {}
            cached_sections = cached.get("sections", {})
            cached_sections[section] = new_content
            await cache_draft(case_id, {"sections": cached_sections, "full_text": cached.get("full_text", "")})

        return {"section": section, "content": new_content}
