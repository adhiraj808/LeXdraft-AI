"""
Master NLP pipeline with RAG support.
Input text → preprocess → NER → classify → RAG retrieve → generate draft
"""

import asyncio
import logging
from typing import Dict, Optional

try:
    import spacy
except ImportError:
    from app.nlp import mock_spacy as spacy

from app.core.config import settings
from app.nlp.classifier import CaseClassifier
from app.nlp.generator import LegalDraftGenerator
from app.nlp.mock_spacy import MockNLP
from app.nlp.ner import LegalNERExtractor
from app.nlp.preprocessor import LegalTextPreprocessor
from app.nlp.retriever import LegalRAGRetriever

logger = logging.getLogger(__name__)


class NLPPipeline:
    def __init__(self):
        self.nlp = None
        self.preprocessor = None
        self.ner = None
        self.classifier = None
        self.generator = None
        self.retriever = None
        self._loaded = False
        # Set when load() has finished (successfully or not) so callers can wait for it.
        self._ready = asyncio.Event()

    async def load(self):
        """
        Load all components. Each heavy, synchronous load call is run in a worker
        thread via asyncio.to_thread so the model-loading window doesn't block the
        event loop (which would otherwise stall startup health checks).
        """
        logger.info("Loading NLP pipeline components...")
        try:
            await self._load_components()
        except Exception:
            logger.exception(
                "NLP pipeline failed to load; drafting is unavailable until restart."
            )
        finally:
            self._ready.set()

    async def _load_components(self):
        try:
            self.nlp = await asyncio.to_thread(spacy.load, settings.SPACY_MODEL)
        except Exception as e:
            logger.warning(
                f"Could not load spacy model {settings.SPACY_MODEL}: {e}. "
                "Using a minimal fallback (no entity extraction) - run: python -m spacy download "
                f"{settings.SPACY_MODEL}"
            )
            self.nlp = MockNLP()

        self.preprocessor = LegalTextPreprocessor(self.nlp)
        self.ner = LegalNERExtractor(self.nlp)

        self.classifier = CaseClassifier()
        try:
            await self.classifier.load()
        except Exception as e:
            logger.warning(f"Failed to load classifier: {e}")

        self.generator = LegalDraftGenerator()
        try:
            await self.generator.load()
        except Exception as e:
            logger.warning(f"Failed to load generator: {e}")

        # RAG (ChromaDB + embeddings) is heavy: it is created now but only *loaded* on
        # first use, unless RAG_EAGER_LOAD=true.
        self.retriever = LegalRAGRetriever()
        if settings.ENABLE_RAG and settings.RAG_EAGER_LOAD:
            try:
                await asyncio.to_thread(self.retriever.ensure_loaded)
            except Exception as e:
                logger.warning(f"Failed to load retriever: {e}")
        elif not settings.ENABLE_RAG:
            logger.info("RAG disabled (ENABLE_RAG=false).")
        else:
            logger.info("RAG will load on first use.")

        self._loaded = True
        logger.info("NLP pipeline loaded (some components might be using fallbacks).")

    async def wait_until_loaded(self, timeout: Optional[float] = 300.0) -> bool:
        """Wait for load() to finish. A draft submitted right after startup waits instead of failing."""
        if not self._ready.is_set():
            try:
                await asyncio.wait_for(self._ready.wait(), timeout)
            except asyncio.TimeoutError:
                pass
        return self._loaded

    def _build_generation_context(
        self,
        case_input: Dict,
        preprocessed: Dict,
        entities: Dict,
        classification: Dict,
        rag_context: str = "",
    ) -> Dict:
        """Build the generation context from FactSheet (preferred) or legacy fields."""
        # Phase 1: Prefer FactSheet when available
        fact_sheet = case_input.get("fact_sheet")

        if fact_sheet and isinstance(fact_sheet, dict):
            # Convert dict back to FactSheet-like access
            fs = fact_sheet
            parties = fs.get("parties", [])

            # relief_sought is now a list of FactField objects
            relief_items = fs.get("relief_sought", [])
            relief_text = ""
            if relief_items:
                relief_vals = [r.get("value") for r in relief_items if r.get("value")]
                relief_text = "; ".join(relief_vals)

            return {
                "case_type": classification["case_type"],
                "petitioner": parties[0].get("name") if parties else case_input.get("petitioner_name", "Petitioner"),
                "respondent": parties[1].get("name") if len(parties) > 1 else case_input.get("respondent_name", "Respondent"),
                "court": entities.get("courts", [None])[0]
                or f"Hon'ble {case_input.get('jurisdiction') or 'High Court'}",
                "description": preprocessed["cleaned"],
                "statutes": list(dict.fromkeys(
                    fs.get("statutes_cited_by_user", []) + preprocessed.get("legal_sections", [])
                )),
                "dates": fs.get("notice_dates", []),
                "incident_date": fs.get("incident_date", {}).get("value") or case_input.get("incident_date") or "the relevant date",
                "location": fs.get("place", {}).get("value") or case_input.get("jurisdiction") or "India",
                "relief_sought": relief_text or case_input.get("relief_sought") or "appropriate relief as deemed fit",
                "money": entities.get("money", []),
                "rag_context": rag_context,
                # FactSheet fields for the generator
                "contract_date": fs.get("contract_date", {}).get("value"),
                "delivery_date": fs.get("delivery_date", {}).get("value"),
                "contract_value": fs.get("contract_value", {}).get("value"),
                "damages_claimed": fs.get("damages_claimed", {}).get("value"),
                "claim_type": fs.get("claim_type", {}).get("value"),  # enum value
                "claim_type_raw": fs.get("claim_type_raw", {}).get("value"),
                "has_arbitration_clause": fs.get("has_arbitration_clause", {}).get("value"),
                "raw_prompt": case_input.get("raw_prompt"),
                "fact_sheet": fs,
            }

        # Legacy fallback
        locations = entities.get("locations", [])
        courts = entities.get("courts", [])
        persons = entities.get("persons", [])
        jurisdiction = case_input.get("jurisdiction") or "India"

        return {
            "case_type": classification["case_type"],
            "petitioner": case_input.get("petitioner_name")
            or (persons[0] if persons else "Petitioner"),
            "respondent": case_input.get("respondent_name")
            or (persons[1] if len(persons) > 1 else "Respondent"),
            "court": courts[0]
            if courts
            else f"Hon'ble {jurisdiction if jurisdiction != 'India' else 'High Court'}",
            "description": preprocessed["cleaned"],
            "statutes": entities.get("statutes", [])
            + preprocessed.get("legal_sections", []),
            "dates": entities.get("dates", []),
            "incident_date": case_input.get("incident_date") or "the relevant date",
            "location": locations[0] if locations else jurisdiction,
            "relief_sought": case_input.get("relief_sought")
            or "appropriate relief as deemed fit",
            "money": entities.get("money", []),
            "rag_context": rag_context,
        }

    def _rag_enabled(self) -> bool:
        return bool(
            self.retriever and settings.ENABLE_RAG and not self.retriever.unavailable
        )

    def _retrieve_precedents(self, query: str, case_type: str, top_k: int) -> str:
        """Sync helper: runs in a thread via asyncio.to_thread (the first call loads RAG)."""
        if not self.retriever.ensure_loaded():
            return ""
        precedents = self.retriever.retrieve(
            query=query, case_type=case_type, top_k=top_k
        )
        if precedents:
            logger.info(f"RAG found {len(precedents)} relevant precedents.")
        else:
            logger.info("RAG found no relevant precedents, using base generation.")
        return self.retriever.format_context(precedents)

    async def process(self, case_input: Dict, strict: bool = False) -> Dict:
        if not self._loaded and not await self.wait_until_loaded():
            raise RuntimeError("NLP pipeline not loaded.")

        text = case_input.get("case_description", "")
        if not text:
            raise ValueError("case_description is required.")

        # All stages below are CPU-bound and synchronous (spaCy, transformer/keyword
        # classification, embedding + ChromaDB query, generation).
        # They run via asyncio.to_thread so a single case being drafted doesn't stall
        # the event loop for every other concurrent request.

        # Stage 1: Preprocess + NER share a single spaCy parse of the cleaned text.
        logger.info("Stage 1: Preprocessing text and extracting entities...")
        cleaned = self.preprocessor.clean_text(text)
        doc = await asyncio.to_thread(self.nlp, cleaned)
        preprocessed = await asyncio.to_thread(self.preprocessor.preprocess, text, doc)
        entities = await asyncio.to_thread(self.ner.extract, cleaned, doc)

        # Stage 2: Classify
        logger.info("Stage 2: Classifying case type...")
        classification = await asyncio.to_thread(self.classifier.classify, text)

        # Stage 3: RAG Retrieval
        logger.info("Stage 3: Retrieving relevant legal precedents...")
        rag_context = ""
        if self._rag_enabled():
            query = f"{classification['case_type']} {text[:500]}"
            rag_context = await asyncio.to_thread(
                self._retrieve_precedents, query, classification["case_type"], 3
            )

        # Stage 4: Build context
        context = self._build_generation_context(
            case_input, preprocessed, entities, classification, rag_context
        )

        # Stage 5: Generate draft
        logger.info("Stage 4: Generating legal draft with RAG context...")
        draft_sections = await self.generator.generate_all_sections(context, strict)

        return {
            "preprocessed": preprocessed,
            "entities": entities,
            "classification": classification,
            "context": context,
            "draft_sections": draft_sections,
            "rag_precedents_used": bool(rag_context),
        }

    async def regenerate_section(
        self,
        section: str,
        case_input: Dict,
        entities: Dict,
        classification: Dict,
        additional_context: Optional[str] = None,
    ) -> str:
        if not self._loaded and not await self.wait_until_loaded():
            raise RuntimeError("NLP pipeline not loaded.")

        description = case_input.get("case_description", "")
        preprocessed = await asyncio.to_thread(
            self.preprocessor.preprocess, description
        )

        # RAG retrieval for regeneration too
        rag_context = ""
        if self._rag_enabled():
            query = f"{classification.get('case_type', '')} {description[:300]}"
            rag_context = await asyncio.to_thread(
                self._retrieve_precedents, query, classification.get("case_type"), 2
            )

        context = self._build_generation_context(
            case_input, preprocessed, entities, classification, rag_context
        )
        if additional_context:
            context["additional_context"] = additional_context

        return await asyncio.to_thread(
            self.generator.generate_section, section, context
        )

    def add_legal_document(
        self, doc_id: str, text: str, case_type: str, topic: str = ""
    ) -> bool:
        """Add a new legal document to the RAG knowledge base (blocking). False if RAG is unavailable."""
        if not self.retriever:
            return False
        added = self.retriever.add_document(doc_id, text, case_type, topic)
        if added:
            logger.info(f"Added document {doc_id} to RAG knowledge base.")
        return added
