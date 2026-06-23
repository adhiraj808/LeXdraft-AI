"""
Text preprocessing for legal case descriptions.
Handles tokenisation, normalisation, and sentence segmentation.
"""

import re
import logging
from typing import List, Dict
try:
    import spacy
except ImportError:
    from app.nlp import mock_spacy as spacy


logger = logging.getLogger(__name__)


class LegalTextPreprocessor:
    """Cleans and normalises raw legal case text for NLP processing."""

    # Legal abbreviations that should not be treated as sentence boundaries
    LEGAL_ABBREVIATIONS = {
        "vs", "v", "u/s", "s", "sec", "art", "cl", "para", "sub", "no",
        "sr", "dr", "mr", "mrs", "ms", "hon", "dist", "insp", "sgt",
        "ipc", "cpc", "crpc", "civ", "crim", "app", "rev", "writ",
    }

    def __init__(self, nlp: spacy.Language):
        self.nlp = nlp

    def clean_text(self, text: str) -> str:
        """Normalise whitespace, fix encoding artifacts, standardise punctuation."""
        # Normalise whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove non-ASCII characters except common legal symbols
        text = re.sub(r'[^\x00-\x7F₹%@&()\[\]{}.,;:\'"!?/\\-]', ' ', text)
        # Normalise quotes
        text = re.sub(r'["""]', '"', text)
        text = re.sub(r"[''']", "'", text)
        # Remove extra punctuation repetitions
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r'-{2,}', ' - ', text)
        return text.strip()

    def segment_sentences(self, text: str, doc=None) -> List[str]:
        """Split text into sentences using spaCy. Reuses `doc` if already parsed."""
        doc = doc if doc is not None else self.nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    def tokenize(self, text: str) -> List[str]:
        """Tokenise text, returning lowercased non-stopword tokens."""
        doc = self.nlp(text.lower())
        return [
            token.lemma_
            for token in doc
            if not token.is_stop and not token.is_punct and token.is_alpha and len(token.text) > 1
        ]

    def extract_legal_sections(self, text: str) -> List[str]:
        """
        Extract IPC / CPC / CrPC section references from text.
        e.g. "Section 420 IPC", "u/s 302 IPC", "Section 498A"
        """
        patterns = [
            r'\b[Ss]ection[s]?\s+\d+[A-Za-z]?\s*(?:of\s+)?(?:IPC|CPC|CrPC|IT Act|POCSO|NDPS)?\b',
            r'\bu/s\s+\d+[A-Za-z]?\b',
            r'\bArt(?:icle)?\.\s*\d+\b',
            r'\bSchedule\s+[IVX]+\b',
        ]
        found = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            found.extend([m.strip() for m in matches])
        return list(set(found))

    def preprocess(self, text: str, doc=None) -> Dict:
        """
        Full preprocessing pipeline.
        Returns a structured dict with cleaned text, sentences, tokens, and extracted sections.
        `doc` may be a spaCy Doc already parsed from `clean_text(text)`, to avoid re-parsing.
        """
        cleaned = self.clean_text(text)
        sentences = self.segment_sentences(cleaned, doc=doc)
        tokens = self.tokenize(cleaned)
        legal_sections = self.extract_legal_sections(text)

        return {
            "original": text,
            "cleaned": cleaned,
            "sentences": sentences,
            "tokens": tokens,
            "legal_sections": legal_sections,
            "word_count": len(cleaned.split()),
            "sentence_count": len(sentences),
        }
