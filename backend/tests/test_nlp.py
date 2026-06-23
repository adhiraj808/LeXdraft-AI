"""Tests for the NLP pipeline components."""

import pytest
from unittest.mock import MagicMock, AsyncMock
import spacy

from app.nlp.preprocessor import LegalTextPreprocessor
from app.nlp.ner import LegalNERExtractor
from app.nlp.classifier import CaseClassifier


@pytest.fixture
def nlp():
    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    return nlp


@pytest.fixture
def preprocessor(nlp):
    return LegalTextPreprocessor(nlp)


@pytest.fixture
def ner(nlp):
    return LegalNERExtractor(nlp)


SAMPLE_TEXT = """
The petitioner Ramesh Kumar filed a complaint against respondent Suresh Sharma
for cheating and fraud under Section 420 IPC and Section 120B IPC on 15th March 2023.
The incident occurred in New Delhi. Damages claimed amount to Rs. 5,00,000.
The matter is before the Delhi High Court.
"""


class TestPreprocessor:

    def test_clean_text(self, preprocessor):
        dirty = "Hello   World\n\nThis  is  a   test..."
        cleaned = preprocessor.clean_text(dirty)
        assert "  " not in cleaned
        assert cleaned == cleaned.strip()

    def test_extract_legal_sections(self, preprocessor):
        sections = preprocessor.extract_legal_sections(SAMPLE_TEXT)
        assert any("420" in s for s in sections)

    def test_preprocess_returns_structure(self, preprocessor):
        result = preprocessor.preprocess(SAMPLE_TEXT)
        assert "cleaned" in result
        assert "sentences" in result
        assert "tokens" in result
        assert "legal_sections" in result
        assert result["word_count"] > 0


class TestNER:

    def test_extract_returns_dict(self, ner):
        result = ner.extract(SAMPLE_TEXT)
        assert isinstance(result, dict)
        for key in ["persons", "organizations", "dates", "locations", "courts", "statutes", "money"]:
            assert key in result

    def test_money_extraction(self, ner):
        result = ner.extract(SAMPLE_TEXT)
        assert len(result["money"]) > 0

    def test_statute_extraction(self, ner):
        result = ner.extract(SAMPLE_TEXT)
        assert len(result["statutes"]) > 0


class TestClassifier:

    def test_keyword_classify_criminal(self):
        clf = CaseClassifier()
        clf.use_model = False
        text = "The accused was arrested for murder under IPC Section 302. FIR was filed."
        result = clf.classify(text)
        assert result["case_type"] == "Criminal"
        assert result["method"] == "keyword"
        assert 0 < result["confidence"] <= 1

    def test_keyword_classify_family(self):
        clf = CaseClassifier()
        clf.use_model = False
        text = "Petition for divorce and child custody. Matrimonial dispute. Maintenance alimony."
        result = clf.classify(text)
        assert result["case_type"] == "Family Law"

    def test_classify_returns_all_fields(self):
        clf = CaseClassifier()
        clf.use_model = False
        result = clf.classify(SAMPLE_TEXT)
        assert "case_type" in result
        assert "confidence" in result
        assert "probabilities" in result
        assert "method" in result
