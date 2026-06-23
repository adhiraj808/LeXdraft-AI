"""
Named Entity Recognition for legal texts.
Extracts persons, organisations, dates, statutes, courts, money amounts.
"""

import logging
import re
from typing import Dict, List
try:
    import spacy
except ImportError:
    from app.nlp import mock_spacy as spacy


logger = logging.getLogger(__name__)


class LegalNERExtractor:
    """
    Extracts named entities from legal case descriptions.
    Uses spaCy's NER plus custom regex patterns for domain-specific entities
    like statute citations and court names.
    """

    COURT_PATTERNS = [
        r"(?:Supreme Court|High Court|District Court|Sessions Court|"
        r"Magistrate Court|Family Court|Labour Court|Consumer Forum|"
        r"Tribunal|NCLAT|NCLT|CAT|SAT)\s*(?:of\s+\w+(?:\s+\w+)?)?"
    ]

    STATUTE_PATTERNS = [
        r"\b(?:Section|Sec\.|S\.)\s*\d+[A-Za-z]?(?:\s*(?:of|r/w|read with)\s*\w[\w\s]*Act(?:\s+\d{4})?)?\b",
        r"\bI\.P\.C\.?\b|\bIPC\b",
        r"\bC\.P\.C\.?\b|\bCPC\b",
        r"\bCr\.P\.C\.?\b|\bCrPC\b",
        r"\b(?:POCSO|NDPS|IT Act|Motor Vehicles Act|Evidence Act|Contract Act|"
        r"Companies Act|Consumer Protection Act|Prevention of Corruption Act)\b",
        r"\bArticle\s+\d+(?:\([a-z]\))?\b",
    ]

    MONEY_PATTERNS = [
        r"(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:lakhs?|crores?|thousands?))?\b",
        r"\b[\d,]+(?:\.\d{2})?\s*(?:lakhs?|crores?)\b",
    ]

    def __init__(self, nlp: spacy.Language):
        self.nlp = nlp

    def _extract_with_regex(self, text: str, patterns: List[str]) -> List[str]:
        """Apply a list of regex patterns and return unique matches."""
        found = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend([m.strip() for m in matches if m.strip()])
        return list(set(found))

    def extract(self, text: str, doc=None) -> Dict[str, List[str]]:
        """
        Run full NER extraction on legal text.
        Returns entities grouped by type.
        `doc` may be a spaCy Doc already parsed from `text`, to avoid re-parsing.
        """
        doc = doc if doc is not None else self.nlp(text)

        # spaCy entity buckets
        persons = []
        organizations = []
        dates = []
        locations = []

        for ent in doc.ents:
            if ent.label_ == "PERSON":
                persons.append(ent.text.strip())
            elif ent.label_ in ("ORG", "FAC"):
                organizations.append(ent.text.strip())
            elif ent.label_ == "DATE":
                dates.append(ent.text.strip())
            elif ent.label_ in ("GPE", "LOC"):
                locations.append(ent.text.strip())

        # Custom legal entities via regex
        courts = self._extract_with_regex(text, self.COURT_PATTERNS)
        statutes = self._extract_with_regex(text, self.STATUTE_PATTERNS)
        money = self._extract_with_regex(text, self.MONEY_PATTERNS)

        # Deduplicate and clean
        return {
            "persons": list(set(persons)),
            "organizations": list(set(organizations)),
            "dates": list(set(dates)),
            "locations": list(set(locations)),
            "courts": list(set(courts)),
            "statutes": list(set(statutes)),
            "money": list(set(money)),
        }

    def get_primary_parties(self, entities: Dict, petitioner_hint: str = None, respondent_hint: str = None) -> Dict:
        """
        Attempt to identify petitioner and respondent from entity list.
        Uses user-provided hints if available.
        """
        persons = entities.get("persons", [])
        orgs = entities.get("organizations", [])
        all_parties = persons + orgs

        petitioner = petitioner_hint or (all_parties[0] if all_parties else "Unknown")
        respondent = respondent_hint or (all_parties[1] if len(all_parties) > 1 else "Unknown")

        return {"petitioner": petitioner, "respondent": respondent}
