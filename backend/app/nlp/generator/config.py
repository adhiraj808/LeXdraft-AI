"""Generator configuration constants."""

from typing import Dict, List, Tuple

# Order in which the 7 sections are generated, stored and exported.
SECTION_ORDER: List[str] = [
    "title_block",
    "complaint_body",
    "prayer",
    "list_of_witnesses",
    "list_of_documents",
    "affidavit",
    "evidence_affidavit",
]

# (section text, source label such as "groq:openai/gpt-oss-20b", "local-llm" or "template")
SectionResult = Tuple[str, str]

# Per-case-type pleading configuration used by the template fallback.
# Each case type gets its own party labels, case number prefix, and substantive narrative.
CASE_TYPE_CONFIG: Dict[str, Dict] = {
    "Criminal": {
        "p_label": "Complainant",
        "r_label": "Accused",
        "case_no_label": "C.C. NO.",
        "show_ps": True,
        "doc_title": "COMPLAINT ON BEHALF OF COMPLAINANT U/S {stat}",
    },
    "Civil": {
        "p_label": "Plaintiff",
        "r_label": "Defendant",
        "case_no_label": "C.S. NO.",
        "show_ps": False,
        "doc_title": "CIVIL SUIT FOR RECOVERY OF {amt} AND DAMAGES U/S {stat}",
    },
    "Family Law": {
        "p_label": "Petitioner",
        "r_label": "Respondent",
        "case_no_label": "H.M.A. PETITION NO.",
        "show_ps": False,
        "doc_title": "PETITION U/S {stat}",
    },
    "Labour / Employment": {
        "p_label": "Workman",
        "r_label": "Management",
        "case_no_label": "I.D. CASE NO.",
        "show_ps": False,
        "doc_title": "PETITION FOR REINSTATEMENT AND BACK WAGES U/S {stat}",
    },
    "Constitutional": {
        "p_label": "Petitioner",
        "r_label": "Respondent",
        "case_no_label": "W.P. NO.",
        "show_ps": False,
        "doc_title": "WRIT PETITION UNDER {stat}",
    },
    "Property Dispute": {
        "p_label": "Plaintiff",
        "r_label": "Defendant",
        "case_no_label": "C.S. NO.",
        "show_ps": False,
        "doc_title": "SUIT FOR POSSESSION AND PERMANENT INJUNCTION U/S {stat}",
    },
}

DEFAULT_CASE_TYPE = "Civil"