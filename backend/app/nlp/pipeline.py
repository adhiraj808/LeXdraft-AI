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
from app.nlp.preprocessor import LegalTextPreprocessor
from app.nlp.ner import LegalNERExtractor
from app.nlp.classifier import CaseClassifier
from app.nlp.generator import LegalDraftGenerator
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

    async def load(self):
        """
        Load all components. Each heavy, synchronous load call is run in a worker
        thread via asyncio.to_thread so the 30-60s model-loading window doesn't
        block the event loop (which would otherwise stall startup health checks).
        """
        logger.info("Loading NLP pipeline components...")

        try:
            self.nlp = await asyncio.to_thread(spacy.load, settings.SPACY_MODEL)
        except Exception as e:
            logger.warning(f"Could not load spacy model {settings.SPACY_MODEL}: {e}. Using mock.")
            self.nlp = spacy.MockNLP() if hasattr(spacy, 'MockNLP') else None

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

        # Load RAG retriever
        self.retriever = LegalRAGRetriever()
        try:
            await asyncio.to_thread(self.retriever.load)
        except Exception as e:
            logger.warning(f"Failed to load retriever: {e}")

        self._loaded = True
        logger.info("NLP pipeline loaded (some components might be using fallbacks).")

    def _build_generation_context(
        self,
        case_input: Dict,
        preprocessed: Dict,
        entities: Dict,
        classification: Dict,
        rag_context: str = "",
    ) -> Dict:
        locations = entities.get("locations", [])
        courts = entities.get("courts", [])
        persons = entities.get("persons", [])

        return {
            "case_type": classification["case_type"],
            "petitioner": case_input.get("petitioner_name") or (persons[0] if persons else "Petitioner"),
            "respondent": case_input.get("respondent_name") or (persons[1] if len(persons) > 1 else "Respondent"),
            "court": courts[0] if courts else f"Hon'ble {case_input.get('jurisdiction', 'High Court')}",
            "description": preprocessed["cleaned"],
            "statutes": entities.get("statutes", []) + preprocessed.get("legal_sections", []),
            "dates": entities.get("dates", []),
            "incident_date": case_input.get("incident_date", "the relevant date"),
            "location": locations[0] if locations else case_input.get("jurisdiction", "India"),
            "relief_sought": case_input.get("relief_sought", "appropriate relief as deemed fit"),
            "money": entities.get("money", []),
            "rag_context": rag_context,
        }

    def _retrieve_precedents(self, query: str, case_type: str, top_k: int) -> str:
        """Sync helper: runs in a thread via asyncio.to_thread."""
        precedents = self.retriever.retrieve(query=query, case_type=case_type, top_k=top_k)
        if precedents:
            logger.info(f"RAG found {len(precedents)} relevant precedents.")
        else:
            logger.info("RAG found no relevant precedents, using base generation.")
        return self.retriever.format_context(precedents)

    async def process(self, case_input: Dict) -> Dict:
        if not self._loaded:
            raise RuntimeError("NLP pipeline not loaded.")

        text = case_input.get("case_description", "")
        if not text:
            raise ValueError("case_description is required.")

        # All stages below are CPU-bound and synchronous (spaCy, transformer/keyword
        # classification, sentence-transformer encoding + ChromaDB query, generation).
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
        if self.retriever and self.retriever._loaded:
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
        draft_sections = await asyncio.to_thread(self.generator.generate_all_sections, context)

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
        if not self._loaded:
            raise RuntimeError("NLP pipeline not loaded.")

        description = case_input.get("case_description", "")
        preprocessed = await asyncio.to_thread(self.preprocessor.preprocess, description)

        # RAG retrieval for regeneration too
        rag_context = ""
        if self.retriever and self.retriever._loaded:
            query = f"{classification.get('case_type', '')} {description[:300]}"
            rag_context = await asyncio.to_thread(
                self._retrieve_precedents, query, classification.get("case_type"), 2
            )

        context = self._build_generation_context(case_input, preprocessed, entities, classification, rag_context)
        if additional_context:
            context["additional_context"] = additional_context

        return await asyncio.to_thread(self.generator.generate_section, section, context)

    def add_legal_document(self, doc_id: str, text: str, case_type: str, topic: str = ""):
        """Add a new legal document to the RAG knowledge base."""
        if self.retriever and self.retriever._loaded:
            self.retriever.add_document(doc_id, text, case_type, topic)
            logger.info(f"Added document {doc_id} to RAG knowledge base.")
