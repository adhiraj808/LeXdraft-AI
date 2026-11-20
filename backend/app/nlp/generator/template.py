"""Template-based draft generation (fallback when no LLM available)."""

from typing import Dict, Optional

from app.nlp.generator.config import (
    SECTION_ORDER,
    CASE_TYPE_CONFIG,
    DEFAULT_CASE_TYPE,
)


def _clip(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] or None


class TemplateGenerator:
    """Generates legal drafts using hardcoded templates (no LLM required)."""

    CASE_TYPE_INSTRUCTIONS = {
        "Criminal": (
            "This is a CRIMINAL complaint. Address the parties as "
            "Complainant and Accused. Use criminal procedure terminology."
        ),
        "Civil": (
            "This is a CIVIL suit. Address the parties as Plaintiff and Defendant. "
            "Use civil procedure terminology (Order 7 Rule 1 CPC for plaint)."
        ),
        "Family Law": (
            "This is a FAMILY LAW petition. Address the parties as Petitioner and Respondent. "
            "Use appropriate family court terminology (HMA, Guardian and Wards Act, etc.)."
        ),
        "Labour / Employment": (
            "This is a LABOUR/EMPLOYMENT dispute. Address the parties as Workman and Management. "
            "Use industrial/labour law terminology (Industrial Disputes Act, etc.)."
        ),
        "Constitutional": (
            "This is a CONSTITUTIONAL writ petition. Address the parties as Petitioner and Respondent. "
            "Use constitutional law terminology (Article 226/32, fundamental rights, etc.)."
        ),
        "Property Dispute": (
            "This is a PROPERTY DISPUTE suit. Address the parties as Plaintiff and Defendant. "
            "Use property law terminology (Specific Relief Act, TPA, etc.)."
        ),
    }

    def _parties_block(self, cfg: dict, p: str, r: str) -> str:
        if cfg.get("show_ps"):
            return f"Complainant : {p}\nAccused      : {r}"
        return f"Plaintiff   : {p}\nDefendant   : {r}"

    def _court_header(self, court: str, loc: str, cfg: dict, yr: str) -> str:
        case_no = f"{cfg['case_no_label']}  ____/ {yr}"
        return f"IN THE COURT OF {court.upper()} AT {loc.upper()}\n{case_no}"

    def _narrative_paragraphs(
        self, case_type: str, p: str, r: str, desc: str, inc: str, amt: str, stat: str, rn: str, fs: Optional[dict] = None
    ) -> str:
        paras = []
        place = _clip(fs.get('place', {}).get('value') if fs else None, 200) if fs else None
        paras.append(f"1. The {self._get_p_label(case_type)} is a resident of {place or 'the jurisdiction of this Hon. Court'}. The {self._get_r_label(case_type)} is a resident of the same area.")
        if inc:
            paras.append(f"2. On or about {inc}, the following incident occurred: {desc}")
        else:
            paras.append(f"2. The incident giving rise to this case is as follows: {desc}")
        if amt:
            paras.append(f"3. The amount involved is Rs. {amt}.")
        if stat:
            paras.append(f"4. The offences/violations fall under: {stat}.")
        if rn:
            paras.append(f"5. The {self._get_r_label(case_type)} is legally bound to {rn.lower()}.")
        return "\n".join(paras)

    def _prayer_text(self, case_type: str, p: str, r: str, relief: str, stat: str, fs: Optional[dict] = None) -> str:
        return f"WHEREFORE, it is most respectfully prayed that this Hon'ble Court may be pleased to:\n(a) {relief or 'grant appropriate relief'};\n(b) pass such other and further orders as this Hon'ble Court may deem fit and proper in the circumstances of the case.\n\nAND FOR THIS ACT OF KINDNESS, THE {self._get_p_label(case_type).upper()} SHALL EVER PRAY."

    def _witnesses_for(self, case_type: str, p: str, fs: Optional[dict] = None) -> str:
        witnesses = [p]
        if fs and fs.get("parties"):
            for party in fs["parties"]:
                if party.get("name") and party["name"] != p:
                    witnesses.append(party["name"])
        return "\n".join(f"{i}. {w}" for i, w in enumerate(witnesses, 1))

    def _documents_for(self, case_type: str, amt: str, inc: str, fs: Optional[dict] = None) -> str:
        docs = ["1. FIR / Complaint copy", "2. Identity proof of parties"]
        if amt:
            docs.append("3. Documents evidencing the amount claimed")
        if inc:
            docs.append("4. Documents relating to the incident date")
        if fs and fs.get("evidence"):
            for ev in fs["evidence"][:3]:
                docs.append(f"{len(docs)+1}. {ev}")
        return "\n".join(docs)

    def _affidavit_body(self, case_type: str, p: str, inc: str, amt: str, stat: str, fs: Optional[dict] = None) -> str:
        return (
            f"I, {p}, the {self._get_p_label(case_type).lower()} herein, do hereby solemnly affirm and declare as under:\n\n"
            f"1. That I am the {self._get_p_label(case_type).lower()} in the above matter and am fully conversant with the facts and circumstances of the case.\n\n"
            f"2. That the contents of the accompanying {self._get_doc_title(case_type, stat)} are true and correct to my knowledge and belief.\n\n"
            f"3. That the incident occurred on or about {inc or 'the relevant date'}.\n\n"
            f"4. That the amount involved is Rs. {amt or 'as claimed'}.\n\n"
            f"5. That the legal provisions applicable are: {stat or 'as per applicable law'}.\n\n"
            f"VERIFICATION:\nVerified at ______ on this ____ day of ______, 20__, that the contents of the above affidavit are true and correct to my knowledge and belief and nothing material has been concealed therefrom.\n\nDEPONENT"
        )

    def _evidence_body(self, case_type: str, p: str, inc: str, amt: str, stat: str, fs: Optional[dict] = None) -> str:
        sd = fs.get("parties", [{}])[0].get("name") if fs and fs.get("parties") else p
        return (
            f"EVIDENCE BY WAY OF AFFIDAVIT\n\n"
            f"I, {sd}, the {self._get_p_label(case_type).lower()} herein, do hereby state on solemn affirmation:\n\n"
            f"1. The facts stated in the {self._get_doc_title(case_type, stat)} are true and correct.\n"
            f"2. The documents filed along with the {self._get_doc_title(case_type, stat)} are genuine and authentic.\n"
            f"3. The evidence relied upon is as per the list of documents filed.\n\n"
            f"DEPONENT"
        )

    def _get_p_label(self, case_type: str) -> str:
        return CASE_TYPE_CONFIG.get(case_type, CASE_TYPE_CONFIG[DEFAULT_CASE_TYPE])["p_label"]

    def _get_r_label(self, case_type: str) -> str:
        return CASE_TYPE_CONFIG.get(case_type, CASE_TYPE_CONFIG[DEFAULT_CASE_TYPE])["r_label"]

    def _get_doc_title(self, case_type: str, stat: str) -> str:
        cfg = CASE_TYPE_CONFIG.get(case_type, CASE_TYPE_CONFIG[DEFAULT_CASE_TYPE])
        return cfg["doc_title"].format(stat=stat or "APPLICABLE LAW", amt="CLAIMED AMOUNT")

    def generate_section(self, section: str, context: Dict) -> str:
        """Generate a single section using template."""
        case_type = context.get("classification", {}).get("case_type") or DEFAULT_CASE_TYPE
        cfg = CASE_TYPE_CONFIG.get(case_type, CASE_TYPE_CONFIG[DEFAULT_CASE_TYPE])

        # Prepare common variables
        p = context.get("petitioner_name") or context.get("title", "").split(" vs ")[0] or "Petitioner"
        r = context.get("respondent_name") or "Respondent"
        inc = context.get("incident_date") or ""
        amt = _clip(context.get("relief_sought"), 200) or ""
        stat = _clip(context.get("sections_alleged"), 200) or ""
        rn = _clip(context.get("relief_sought"), 500) or ""
        fs = context.get("fact_sheet")

        if section == "title_block":
            return f"{self._court_header(context.get('jurisdiction', 'District Court'), context.get('jurisdiction', 'City'), cfg, '2025')}\n\n{cfg['doc_title'].format(stat=stat or 'APPLICABLE LAW', amt=amt or 'CLAIMED AMOUNT')}\n\n{self._parties_block(cfg, p, r)}"
        elif section == "complaint_body":
            return self._narrative_paragraphs(case_type, p, r, context.get("case_description", ""), inc, amt, stat, rn, fs)
        elif section == "prayer":
            return self._prayer_text(case_type, p, r, relief=context.get("relief_sought", ""), stat=stat, fs=fs)
        elif section == "list_of_witnesses":
            return self._witnesses_for(case_type, p, fs)
        elif section == "list_of_documents":
            return self._documents_for(case_type, amt, inc, fs)
        elif section == "affidavit":
            return self._affidavit_body(case_type, p, inc, amt, stat, fs)
        elif section == "evidence_affidavit":
            return self._evidence_body(case_type, p, inc, amt, stat, fs)
        return f"[MISSING SECTION: {section}]"

    def generate_all_sections(self, context: Dict) -> Dict[str, str]:
        """Generate all 7 sections."""
        return {section: self.generate_section(section, context) for section in SECTION_ORDER}