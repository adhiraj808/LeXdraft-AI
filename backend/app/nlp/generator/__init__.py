"""Legal Draft Generator — split modules."""

from app.nlp.generator.generator import LegalDraftGenerator
from app.nlp.generator.config import (
    SECTION_ORDER,
    CASE_TYPE_CONFIG,
    DEFAULT_CASE_TYPE,
)

__all__ = [
    "LegalDraftGenerator",
    "SECTION_ORDER",
    "CASE_TYPE_CONFIG",
    "DEFAULT_CASE_TYPE",
]