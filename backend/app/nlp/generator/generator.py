"""Legal Draft Generator — Main orchestrator combining cloud, local, and template generators."""

import asyncio
import logging
import time
from typing import Dict

from app.core.config import settings
from app.nlp.generator.config import (
    SECTION_ORDER,
    DEFAULT_CASE_TYPE,
    SectionResult,
)
from app.nlp.generator.cloud import CloudGenerator
from app.nlp.generator.local import LocalGenerator
from app.nlp.generator.template import TemplateGenerator

logger = logging.getLogger(__name__)


class LegalDraftGenerator:
    """Model-agnostic legal draft generator.

    Generation flow per section:
      1. CHECK classification (case type) — falls back to Civil if unknown.
      2. Build a case-type-aware prompt (correct party labels, doc title, format).
      3. Try the resolved cloud LLM (any OpenAI-compatible provider).
      4. Fall back to local GGUF, then to hardcoded templates.
    """

    # Case-type-specific drafting instructions injected into every LLM prompt
    CASE_TYPE_INSTRUCTIONS = {
        "Criminal": (
            "This is a CRIMINAL complaint. Address the parties as "
            "Complainant and Accused. Use criminal procedure terminology. "
            "Follow CrPC format. Include sections, prayer for FIR/arrest/bail as appropriate."
        ),
        "Civil": (
            "This is a CIVIL suit. Address the parties as Plaintiff and Defendant. "
            "Use civil procedure terminology (Order 7 Rule 1 CPC for plaint). "
            "Include valuation, court fee, jurisdiction, cause of action, relief sought."
        ),
        "Family Law": (
            "This is a FAMILY LAW petition. Address the parties as Petitioner and Respondent. "
            "Use appropriate family court terminology (HMA, Guardian and Wards Act, etc.). "
            "Include marriage details, children, grounds, interim relief."
        ),
        "Labour / Employment": (
            "This is a LABOUR/EMPLOYMENT dispute. Address the parties as Workman and Management. "
            "Use industrial/labour law terminology (Industrial Disputes Act, etc.). "
            "Include service details, dispute timeline, relief (reinstatement/back wages)."
        ),
        "Constitutional": (
            "This is a CONSTITUTIONAL writ petition. Address the parties as Petitioner and Respondent. "
            "Use constitutional law terminology (Article 226/32, fundamental rights, etc.). "
            "Include violation of rights, urgency, alternative remedy exhausted."
        ),
        "Property Dispute": (
            "This is a PROPERTY DISPUTE suit. Address the parties as Plaintiff and Defendant. "
            "Use property law terminology (Specific Relief Act, TPA, etc.). "
            "Include property description, title chain, possession details, injunction prayer."
        ),
    }

    def __init__(self):
        self.cloud = CloudGenerator()
        self.local = LocalGenerator()
        self.template = TemplateGenerator()
        self._loaded = False

    async def load(self):
        """Initialize any async resources."""
        self._loaded = True

    def check_case_type(self, ctx: Dict) -> str:
        """Extract case type from context, fall back to Civil."""
        classification = ctx.get("classification", {})
        case_type = classification.get("case_type") if isinstance(classification, dict) else None
        return case_type or DEFAULT_CASE_TYPE

    def _section_prompt(self, section: str, ctx: Dict) -> str:
        """Build a case-type-aware prompt for a specific section."""
        case_type = self.check_case_type(ctx)
        instruction = self.CASE_TYPE_INSTRUCTIONS.get(case_type, self.CASE_TYPE_INSTRUCTIONS["Civil"])

        # Extract relevant fields
        p = ctx.get("petitioner_name") or "Petitioner"
        r = ctx.get("respondent_name") or "Respondent"
        desc = ctx.get("case_description") or ""
        inc = ctx.get("incident_date") or ""
        amt = ctx.get("relief_sought") or ""
        stat = ctx.get("sections_alleged") or ""
        jurisdiction = ctx.get("jurisdiction") or "District Court"

        # FactSheet fields
        fs = ctx.get("fact_sheet", {})
        parties = fs.get("parties", []) if fs else []
        statutes = fs.get("statutes_cited_by_user", []) if fs else []
        relief = fs.get("relief_sought", {}).get("value", "") if fs else ""

        section_names = {
            "title_block": "Title Block & Case Caption (court, case number, parties)",
            "complaint_body": "Complaint Body - narrate facts, cause of action, legal basis",
            "prayer": "Prayer - specific relief sought from the court",
            "list_of_witnesses": "List of Witnesses with names and relevance",
            "list_of_documents": "List of Documents relied upon",
            "affidavit": "Affidavit/Verification by the complainant/petitioner",
            "evidence_affidavit": "Evidence by Way of Affidavit (supplementary)",
        }

        prompt = f"""You are an expert Indian legal draftsperson. Generate ONLY the "{section_names.get(section, section)}" section.

{instruction}

CASE CONTEXT:
- Case Type: {case_type}
- Court: {jurisdiction}
- Petitioner/Complainant: {p}
- Respondent/Accused: {r}
- Incident Date: {inc}
- Amount/Claim: {amt}
- Statutes: {stat}
- Facts: {desc}
- FactSheet Parties: {", ".join([pr.get("name", "") for pr in parties]) if parties else "N/A"}
- FactSheet Statutes: {", ".join(statutes) if statutes else "N/A"}
- FactSheet Relief: {relief}

REQUIREMENTS:
- Use correct legal format for {case_type} cases
- Reference specific statutes and case law where appropriate
- Use formal legal language
- Output ONLY the {section} section content
- No markdown, no explanations, no extra text"""

        return prompt

    def _prepare_context(self, ctx: Dict) -> Dict:
        """Ensure context has all required fields with defaults."""
        return {
            "classification": ctx.get("classification", {}),
            "petitioner_name": ctx.get("petitioner_name", "Petitioner"),
            "respondent_name": ctx.get("respondent_name", "Respondent"),
            "case_description": ctx.get("case_description", ""),
            "incident_date": ctx.get("incident_date", ""),
            "relief_sought": ctx.get("relief_sought", ""),
            "sections_alleged": ctx.get("sections_alleged", ""),
            "jurisdiction": ctx.get("jurisdiction", "District Court"),
            "fact_sheet": ctx.get("fact_sheet", {}),
            "raw_prompt": ctx.get("raw_prompt", ""),
        }

    def _model_name(self) -> str:
        """Human-readable label for which generator produced a draft."""
        if self.cloud._cloud_usable():
            for p in self.cloud._provider_order():
                if p == "groq":
                    return f"groq:{settings.GROQ_MODEL}"
                elif p == "hf":
                    return f"hf:{settings.HF_MODEL}"
                elif p == "llm":
                    return f"llm:{settings.LLM_MODEL}"
        if self.local.is_available():
            return "local-llm"
        return "template"

    async def _generate_section_with_source(self, section: str, ctx: Dict) -> SectionResult:
        """Try cloud -> local -> template, return (text, source_label)."""
        prompt = self._section_prompt(section, ctx)
        max_tokens = settings.LLM_MAX_TOKENS

        # 1. Try cloud LLM
        if self.cloud._cloud_usable():
            result = await self.cloud.generate(prompt, max_tokens)
            if result:
                # Find which provider actually succeeded
                for p in self.cloud._provider_order():
                    if not self.cloud._is_provider_failed(p):
                        return result, f"{p}:{getattr(settings, f'{p.upper()}_MODEL', p)}"
                return result, "cloud"

        # 2. Try local GGUF
        if self.local.is_available():
            result = await self.local.generate_async(prompt, max_tokens)
            if result:
                return result, "local-llm"

        # 3. Fallback to template
        template_text = self.template.generate_section(section, ctx)
        return template_text, "template"

    async def generate_all_sections(self, context: Dict, strict: bool = False) -> Dict:
        """Generate all 7 sections with source tracking."""
        ctx = self._prepare_context(context)
        self.check_case_type(ctx)  # Validates case type
        sections = {}
        sources = {}
        start_time = time.time()

        for section in SECTION_ORDER:
            text, source = await self._generate_section_with_source(section, ctx)
            sections[section] = text
            sources[section] = source

            # Small delay between sections to respect rate limits
            await asyncio.sleep(settings.LLM_SECTION_DELAY_SECONDS)

        # Add metadata
        gen_time = round(time.time() - start_time, 2)
        sections["_model_used"] = self._model_name()
        sections["_generation_time_seconds"] = gen_time
        sections["_full_text"] = "\n\n".join(sections[s] for s in SECTION_ORDER)
        sections["_section_sources"] = sources

        return sections

    def generate_section(self, section: str, context: Dict) -> str:
        """Synchronous template-only generation (for testing/fallback)."""
        ctx = self._prepare_context(context)
        return self.template.generate_section(section, ctx)

    def use_groq(self) -> bool:
        return self.cloud._provider_has_credentials("groq") and not self.cloud._is_provider_failed("groq")

    def use_hf(self) -> bool:
        return self.cloud._provider_has_credentials("hf") and not self.cloud._is_provider_failed("hf")

    def _effective_provider(self) -> str:
        if self.cloud._cloud_usable():
            for p in self.cloud._provider_order():
                if not self.cloud._is_provider_failed(p):
                    return p
        if self.local.is_available():
            return "local"
        return "template"

    @property
    def model_label(self) -> str:
        return self._model_name()