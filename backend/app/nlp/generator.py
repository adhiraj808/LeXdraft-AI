"""Legal Draft Generator — Phase 2: FactSheet-driven, review notes, MISSING placeholders.

This is a compatibility wrapper that re-exports from the split generator package.
"""

from app.nlp.generator import (
    LegalDraftGenerator,
    SECTION_ORDER,
    CASE_TYPE_CONFIG,
    DEFAULT_CASE_TYPE,
)

# Re-export for backward compatibility
__all__ = [
    "LegalDraftGenerator",
    "SECTION_ORDER",
    "CASE_TYPE_CONFIG",
    "DEFAULT_CASE_TYPE",
]