"""Legal Draft Generator — Phase 2: FactSheet-driven, review notes, MISSING placeholders."""

import asyncio
import datetime
import importlib.util
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.nlp.fact_sheet import missing_marker

logger = logging.getLogger(__name__)

# Order in which the 7 sections are generated, stored and exported.
SECTION_ORDER = [
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


# Per-case-type pleading configuration used by the template fallback (when no
# GGUF model is loaded). Each case type gets its own party labels, case number
# prefix, and substantive narrative — without this, every case type produced
# the same NI Act cheque-dishonour criminal complaint text regardless of what
# the classifier actually determined the case to be.
CASE_TYPE_CONFIG = {
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


class LegalDraftGenerator:
    """Model-agnostic legal draft generator.

    Generation flow per section:
      1. CHECK classification (case type) — falls back to Civil if unknown.
      2. Build a case-type-aware prompt (correct party labels, doc title,
         format for Civil / Criminal / Family / etc.).
      3. Try the resolved cloud LLM (any OpenAI-compatible provider).
      4. Fall back to local GGUF, then to hardcoded templates.
    """

    # Case-type-specific drafting instructions injected into every LLM prompt
    # so ANY model produces correctly-formatted, case-type-appropriate output.
    CASE_TYPE_INSTRUCTIONS = {
        "Criminal": (
            "This is a CRIMINAL complaint. Address the parties as "
            "'Complainant' and 'Accused'. Reference the police station, the "
            "dishonour/offence facts, and prosecution under the alleged "
            "sections. Use criminal-complaint formatting."
        ),
        "Civil": (
            "This is a CIVIL suit. Address the parties as 'Plaintiff' and "
            "'Defendant'. Focus on breach, loss/damages, recovery, and "
            "territorial+pecuniary jurisdiction. Use plaint formatting."
        ),
        "Family Law": (
            "This is a FAMILY LAW petition (e.g. divorce/maintenance under "
            "HMA/DV Act). Address the parties as 'Petitioner' and "
            "'Respondent'. Cover marriage facts, cruelty/desertion grounds, "
            "custody/maintenance where relevant. Use petition formatting."
        ),
        "Labour / Employment": (
            "This is an INDUSTRIAL/labour dispute. Address the parties as "
            "'Workman' and 'Management'. Cover termination, retrenchment, "
            "back wages, and industrial-adjudication formatting."
        ),
        "Constitutional": (
            "This is a WRIT PETITION under the Constitution. Address the "
            "parties as 'Petitioner' and 'Respondent (State/authority)'. "
            "Frame fundamental/legal-rights violations and the relief sought "
            "from the High Court/Supreme Court."
        ),
        "Property Dispute": (
            "This is a PROPERTY dispute. Address the parties as 'Plaintiff' "
            "and 'Defendant'. Cover title, possession, encroachment, "
            "injunction, and property-valuation facts."
        ),
    }

    def __init__(self):
        self.use_model = False  # True once the local GGUF model has been loaded
        self.llm = None
        self._llm_lock = (
            threading.Lock()
        )  # serialises GGUF loading and inference (not thread-safe)
        self._llm_load_failed = False
        from app.nlp.llm_client import build_default_clients, resolve_provider

        self._clients = build_default_clients()
        self._provider = resolve_provider(self._clients)
        self.client = self._clients.get(self._provider) if self._provider else None
        # Circuit breaker: provider name -> time.monotonic() until which it is skipped.
        self._cooldown_until: Dict[str, float] = {}

    def _mark_provider_failed(self, provider: str):
        """Skip a provider for LLM_FAILURE_COOLDOWN_SECONDS after a failed call.

        A temporary pause (not a permanent ban): one rate-limit or timeout must not turn
        the LLM off for every later draft until the server restarts.
        """
        cooldown = settings.LLM_FAILURE_COOLDOWN_SECONDS
        self._cooldown_until[provider] = time.monotonic() + cooldown
        logger.warning(
            f"LLM provider '{provider}' failed; skipping it for {cooldown:.0f}s."
        )

    def _is_provider_failed(self, provider: str) -> bool:
        """True while the provider is in its post-failure cooldown."""
        return time.monotonic() < self._cooldown_until.get(provider, 0.0)

    async def load(self):
        if self.client and self.client.available:
            logger.info(
                f"Cloud LLM ready via '{self._provider}' (model={self.client.model})."
            )
        else:
            logger.info(
                "No cloud LLM configured: drafts use the local model (if enabled) or templates."
            )

        if not settings.ENABLE_LOCAL_LLM:
            logger.info("Local GGUF model disabled (ENABLE_LOCAL_LLM=false).")
            return
        if importlib.util.find_spec("llama_cpp") is None:
            logger.warning(
                "ENABLE_LOCAL_LLM=true but llama-cpp-python is not installed "
                "(pip install -r requirements-local-llm.txt)."
            )
            return

        model_path = settings.resolve_backend_path(settings.GGUF_MODEL_PATH)
        if not os.path.exists(model_path):
            logger.warning(f"GGUF model not found at {model_path}.")
            return

        # Loading ~1 GB into RAM is deferred until a draft actually needs it.
        logger.info(f"GGUF model found at {model_path} (loaded lazily on first use).")

    def check_case_type(self, ctx: Dict) -> str:
        """Classification gate — validate the case type BEFORE generating.

        The classifier runs upstream (pipeline stage 2) and passes the result
        in ctx['case_type']. Here we verify it against the known legal
        categories; anything unknown or missing falls back to Civil (the
        generic plaint format), which is safe for any set of facts.
        """
        case_type = (ctx.get("case_type") or "").strip()
        if not case_type:
            logger.warning("No case_type in context — defaulting to 'Civil'.")
            return DEFAULT_CASE_TYPE if DEFAULT_CASE_TYPE != "auto" else "Civil"
        if (
            case_type not in CASE_TYPE_CONFIG
            and case_type not in self.CASE_TYPE_INSTRUCTIONS
        ):
            logger.warning(f"Unknown case_type '{case_type}' — defaulting to 'Civil'.")
            return "Civil"
        return case_type

    def _ensure_local_llm(self) -> bool:
        """Load the local GGUF model on first use. Blocking: call from a worker thread."""
        if self.llm is not None:
            return True
        if not settings.ENABLE_LOCAL_LLM or self._llm_load_failed:
            return False

        with self._llm_lock:
            if self.llm is not None:
                return True
            if self._llm_load_failed:
                return False
            try:
                from llama_cpp import Llama
            except ImportError:
                logger.warning(
                    "llama-cpp-python is not installed; local model disabled."
                )
                self._llm_load_failed = True
                return False

            model_path = settings.resolve_backend_path(settings.GGUF_MODEL_PATH)
            if not os.path.exists(model_path):
                logger.warning(
                    f"GGUF model not found at {model_path}; local model disabled."
                )
                self._llm_load_failed = True
                return False

            try:
                logger.info(f"Loading GGUF model from {model_path}...")
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=settings.GGUF_CONTEXT_WINDOW,
                    # Physical cores, not hyper-threads: more threads only add contention.
                    n_threads=max(1, (os.cpu_count() or 2) // 2),
                    n_gpu_layers=settings.GGUF_GPU_LAYERS,
                    verbose=False,
                )  # the file is memory-mapped by default, so the OS can page it out under pressure
                self.use_model = True
                logger.info(
                    f"GGUF model loaded (n_ctx={settings.GGUF_CONTEXT_WINDOW}, "
                    f"n_gpu_layers={settings.GGUF_GPU_LAYERS})."
                )
                return True
            except Exception as e:
                logger.error(f"Failed to load GGUF model: {e}")
                self._llm_load_failed = True
                return False

    def _generate_with_llm(self, section: str, ctx: Dict) -> Optional[str]:
        """Draft one section with the local GGUF model (same prompt as the cloud path)."""
        messages = [
            {"role": "system", "content": "You are an expert Indian legal draftsman. Temperature 0.2 — be precise and factual."},
            {"role": "user", "content": self._section_prompt(section, ctx)},
        ]
        try:
            with self._llm_lock:  # llama.cpp contexts are not thread-safe
                # create_chat_completion applies the chat template stored in the GGUF file.
                output = self.llm.create_chat_completion(
                    messages=messages,
                    max_tokens=min(1024, max(256, settings.GGUF_CONTEXT_WINDOW // 2)),
                    temperature=0.2,
                    top_p=0.9,
                )
            text = (output["choices"][0]["message"].get("content") or "").strip()
            return text or None
        except Exception as e:
            logger.error(f"Local LLM generation failed: {e}")
            return None

    def _section_prompt(self, section: str, ctx: Dict) -> str:
        """Shared prompt builder for online LLM drafting.

        The case type is validated FIRST (classification gate) and its
        drafting instructions are injected, so ANY model produces output
        formatted for the right legal category (Civil / Criminal / ...).
        """
        case_type = self.check_case_type(ctx)

        # Prefer FactSheet when available
        fact_sheet = ctx.get("fact_sheet")
        raw_prompt = ctx.get("raw_prompt", "")

        if fact_sheet and isinstance(fact_sheet, dict):
            fs = fact_sheet
            parties = fs.get("parties", [])
            petitioner = parties[0].get("name") if parties else ctx.get("petitioner", "Petitioner")
            respondent = parties[1].get("name") if len(parties) > 1 else ctx.get("respondent", "Respondent")

            # Use exact party names as typed (no suffixes added)
            p = petitioner
            r = respondent

            # Party roles from FactSheet (INFERRED)
            pet_role = parties[0].get("role", "plaintiff") if parties else "plaintiff"
            resp_role = parties[1].get("role", "defendant") if len(parties) > 1 else "defendant"

            # Relief sought as list
            relief_items = fs.get("relief_sought", [])
            relief_text = "; ".join([r.get("value") for r in relief_items if r.get("value")]) if relief_items else ctx.get("relief_sought", "")

            # Statutes from FactSheet (whitelisted only)
            statutes = fs.get("statutes_cited_by_user", [])
            stat = ", ".join(statutes) if statutes else "applicable provisions of law"

            # Claim type
            claim_type_raw = fs.get("claim_type_raw", {}).get("value", "")
            claim_type_enum = fs.get("claim_type", {}).get("value", "")

            # Contract/incident dates
            contract_date = fs.get("contract_date", {}).get("value")
            incident_date = fs.get("incident_date", {}).get("value") or fs.get("contract_date", {}).get("value")

            # Money
            contract_value = fs.get("contract_value", {}).get("value")
            damages_claimed = fs.get("damages_claimed", {}).get("value")

            # Place
            location = fs.get("place", {}).get("value")

            # Court
            court = ctx.get("court", "HON'BLE COURT")

            # Description
            desc = ctx.get("description", "")
        else:
            # Legacy fallback
            p = ctx.get("petitioner", "Petitioner")
            r = ctx.get("respondent", "Respondent")
            court = ctx.get("court", "HON'BLE COURT")
            loc = ctx.get("location", "Delhi")
            desc = ctx.get("description", "")
            relief = ctx.get("relief_sought", "appropriate relief as deemed fit")
            sl = ctx.get("statutes", [])
            stat = ", ".join(sl) if sl else "applicable provisions of law"
            p_label = "Plaintiff"
            r_label = "Defendant"
            contract_date = ctx.get("contract_date")
            incident_date = ctx.get("incident_date")
            contract_value = ctx.get("contract_value")
            damages_claimed = ctx.get("damages_claimed")
            location = ctx.get("location", "Delhi")
            claim_type_raw = ""
            claim_type_enum = ""
            relief_items = []

        type_instruction = self.CASE_TYPE_INSTRUCTIONS.get(case_type, "")

        # Build the prompt with FactSheet data
        prompt_parts = [
            "You are an expert Indian legal draftsman. Draft ONLY the",
            f"'{section.replace('_', ' ')}' section of a legal pleading for a",
            f"{case_type} case in India, using proper format and terminology.",
            "",
            f"Category instruction: {type_instruction}",
            f"Case Type: {case_type}",
        ]

        # Party info with exact names from FactSheet
        prompt_parts.append(f"Petitioner: {p}")
        prompt_parts.append(f"Respondent: {r}")
        prompt_parts.append(f"Party Roles (INFERRED): Petitioner={pet_role if 'pet_role' in locals() else 'plaintiff'}, Respondent={resp_role if 'resp_role' in locals() else 'defendant'}")
        prompt_parts.append("IMPORTANT: Use party names EXACTLY as given above. Do not add 'Ltd', 'Pvt Ltd', 'Limited', or any suffixes.")
        prompt_parts.append("REVIEW NOTE: Exact legal names and entity types to be confirmed.")

        prompt_parts.append(f"Court: {court}")
        prompt_parts.append(f"Location: {location}")
        prompt_parts.append(f"Facts: {desc}")

        if contract_date:
            prompt_parts.append(f"Contract Date: {contract_date}")
        if incident_date:
            prompt_parts.append(f"Incident Date: {incident_date}")
        if contract_value:
            prompt_parts.append(f"Contract Value: {contract_value}")
        if damages_claimed:
            prompt_parts.append(f"Damages Claimed: {damages_claimed}")
        else:
            prompt_parts.append("Damages Claimed: [TO BE CONFIRMED: damages claimed]")

        prompt_parts.append(f"Claim Type: {claim_type_enum if claim_type_enum else 'Unknown'}")
        if claim_type_raw:
            prompt_parts.append(f"Claim Description: {claim_type_raw}")

        prompt_parts.append(f"Statutes Cited: {stat}")
        prompt_parts.append("IMPORTANT: Cite ONLY whitelisted statutes. Do not cite Section 73 for specific performance.")
        prompt_parts.append("REVIEW NOTE: Section 73 applies to damages only; specific performance is under SRA ss.10/14/16.")

        if relief_items:
            prompt_parts.append(f"Relief Sought: {relief_text}")

        prompt_parts.append(f"Relevant precedents:\n{ctx.get('rag_context', '')}")
        prompt_parts.append("")
        prompt_parts.append("OUTPUT RULES:")
        prompt_parts.append("1. Use ONLY facts from this prompt. Never invent names, dates, amounts, clause numbers, addresses, or witnesses.")
        prompt_parts.append("2. For any MISSING fact, write [TO BE CONFIRMED: field name] exactly.")
        prompt_parts.append("3. Party names must match EXACTLY as given. No added suffixes (Ltd, Pvt Ltd, etc.).")
        prompt_parts.append("4. Contract value and damages claimed are SEPARATE. Do not equate them.")
        prompt_parts.append("5. Cite ONLY whitelisted statutes. Each relief must cite its correct section.")
        prompt_parts.append("6. Do not list defendant's witnesses in plaintiff's witness list.")
        prompt_parts.append("7. Statutes and case law are NOT exhibits.")
        prompt_parts.append("8. No 'confirm jurisdiction' prayer.")
        prompt_parts.append("9. Temperature 0.2 — be precise and factual.")
        prompt_parts.append("")
        prompt_parts.append("Output the section text only, no explanations.")

        return "\n".join(prompt_parts)

    def _cloud_usable(self) -> bool:
        return bool(self.client and self.client.available)

    def _provider_order(self) -> List[str]:
        """Resolved primary provider first, then the other configured ones."""
        order = [self._provider] if self._provider in self._clients else []
        order += [
            name
            for name in ("openai", "hf", "groq")
            if name in self._clients and name not in order
        ]
        return order

    def _generate_with_cloud(
        self, section: str, ctx: Dict, retries: int = 0
    ) -> Optional[SectionResult]:
        """Draft one section through the cloud provider chain.

        Primary provider first, then the other configured providers; a provider that is in
        its failure cooldown is skipped. Returns (text, "provider:model"), or None when no
        provider produced text. Blocking: call from a worker thread.
        """
        if not self._cloud_usable():  # also covers MODEL_PROVIDER=local/template
            return None

        messages = [
            {"role": "system", "content": "You are an expert Indian legal draftsman. Temperature 0.2 — be precise and factual."},
            {"role": "user", "content": self._section_prompt(section, ctx)},
        ]
        for name in self._provider_order():
            client = self._clients[name]
            if not client.available or self._is_provider_failed(name):
                continue
            text = client.chat(messages, temperature=0.2, retries=retries)
            if text:
                return text, f"{name}:{client.model}"
            self._mark_provider_failed(name)

        logger.warning("No cloud LLM produced text for '%s'.", section)
        return None

    def _parties_block(self, cfg, p, r):
        """Shared 'IN THE MATTER OF ... Versus ...' block used by most sections."""
        return (
            f"IN THE MATTER OF:\n\n{p}\n\t\t\t\t……………………………………{cfg['p_label']}\n\n"
            f"Versus\n\n{r}\n\t\t\t\t……………………………………………{cfg['r_label']}\n\n"
        )

    def _court_header(self, court, loc, cfg, yr):
        return f"IN THE COURT OF {court.upper()}\n{loc.upper()} COURTS\n\n{cfg['case_no_label']} …………..{yr}\n\n"

    def _narrative_paragraphs(self, case_type, p, r, desc, inc, amt, stat, rn, fs=None, review_note_parties="", review_note_roles=""):
        """Case-type-specific cause-of-action narrative for the main pleading body."""
        # MISSING placeholders
        contract_date = self._get_fs_field(fs, "contract_date", "contract date") if fs else "contract date"
        incident_date = self._get_fs_field(fs, "incident_date", "incident date") if fs else "incident date"
        self._get_fs_field(fs, "contract_value", "contract value") if fs else "contract value"
        self._get_fs_field(fs, "damages_claimed", "damages claimed") if fs else "damages claimed"
        self._get_fs_field(fs, "delivery_date", "delivery date") if fs else "delivery date"
        self._get_fs_field(fs, "notice_dates", "notice date") if fs else "notice date"
        self._get_fs_field(fs, "claim_type", "claim type") if fs else "claim type"
        self._get_fs_field(fs, "place", "place") if fs else "place"
        ", ".join(fs.get("statutes_cited_by_user", [])) if fs else "applicable provisions of law"

        # For complaint body, use contract_value as amt, but separate damages
        contract_amt = self._get_fs_field(fs, "contract_value", "contract value") if fs else "contract value"
        damages_amt = self._get_fs_field(fs, "damages_claimed", "damages claimed") if fs else "damages claimed"

        # Use incident_date if available, else contract_date, else inc
        effective_inc = incident_date if incident_date != "[TO BE CONFIRMED: incident date]" else (contract_date if contract_date != "[TO BE CONFIRMED: contract date]" else inc)

        if case_type == "Criminal":
            return (
                f"1.\tThat the Complainant, {p}, through its Authorised Representative, is well conversant with the facts and circumstances of the present complaint and is duly authorised to represent and sign this complaint before this Hon’ble Court.\n\n"
                f"2.\tThat the Complainant is a reputed firm/individual engaged in lawful business. The Accused, {r}, was known to the Complainant and the following events transpired between the parties:\n\n{desc}\n\n"
                f"3.\tThat the Accused issued a cheque/instrument dated {effective_inc} for a sum of {contract_amt} in favour of the Complainant to discharge their lawful liability. The said instrument was duly presented for realisation but was returned/dishonoured. The original cheque is annexed as Annexure C and the cheque returning memo is annexed as Annexure D.\n\n"
                f"4.\tThat the Complainant caused a legal demand notice to be served upon the Accused. The Accused failed to pay within the stipulated 15 days. The copy of legal notice is annexed as Annexure E. The postal receipt and POD is annexed as Annexure F. The copy of email is annexed as Annexure G.\n\n"
                f"5.\tThat the Accused is liable to be prosecuted u/s {stat}. The cause of action arose on each date of transaction, on dishonour of the cheque, and on failure to comply with the legal notice, all within the jurisdiction of this Hon’ble Court.\n\n"
                f"6.\tThat this Hon’ble Court has full territorial and pecuniary jurisdiction to try and decide this complaint. The complaint is filed within the period of limitation under {stat}.{rn}"
            )
        if case_type == "Family Law":
            return (
                f"1.\tThat the Petitioner, {p}, is the lawfully wedded spouse of the Respondent, {r}, and is well conversant with the facts and circumstances of the present petition.\n\n"
                f"2.\tThat the marriage between the parties was solemnised according to law, and the following events transpired during the subsistence of the marriage:\n\n{desc}\n\n"
                f"3.\tThat the conduct of the Respondent, more particularly described above, amounts to cruelty/desertion within the meaning of {stat}, rendering it impossible for the Petitioner to continue to reside with the Respondent.\n\n"
                f"4.\tThat the cause of action arose on {effective_inc} and has continued since, within the territorial jurisdiction of this Hon’ble Court, where the parties last resided together / where the marriage was solemnised.\n\n"
                f"5.\tThat this Hon’ble Family Court has full jurisdiction to try and decide this petition under {stat}, and the petition is filed within the period of limitation, if any.{rn}"
            )
        if case_type == "Labour / Employment":
            return (
                f"1.\tThat the Workman, {p}, was employed by the Management, {r}, and is well conversant with the facts and circumstances of the present petition.\n\n"
                f"2.\tThat during the course of employment, the following events transpired leading to the present industrial dispute:\n\n{desc}\n\n"
                f"3.\tThat the termination/dismissal of the Workman effected by the Management on {effective_inc} was done without following the mandatory procedure, notice, and retrenchment compensation of {contract_amt} required under {stat}, and is therefore illegal and void ab initio.\n\n"
                f"4.\tThat the cause of action arose on the date of termination and continues, within the jurisdiction of this Hon’ble Labour Court/Industrial Tribunal.\n\n"
                f"5.\tThat this Hon’ble Court/Tribunal has full jurisdiction to adjudicate this dispute under {stat}.{rn}"
            )
        if case_type == "Constitutional":
            return (
                f"1.\tThat the Petitioner, {p}, is a citizen of India whose fundamental/legal rights have been violated by the action of the Respondent, {r}, a State/statutory authority within the meaning of Article 12 of the Constitution.\n\n"
                f"2.\tThat the facts giving rise to the violation are as under:\n\n{desc}\n\n"
                f"3.\tThat the impugned action/order dated {effective_inc} is in violation of {stat} and is liable to be quashed/set aside as being arbitrary, unconstitutional, and without authority of law.\n\n"
                f"4.\tThat the Petitioner has no other equally efficacious remedy except to approach this Hon’ble Court by way of this writ petition, and the cause of action arose within the jurisdiction of this Hon’ble Court.\n\n"
                f"5.\tThat this Hon’ble Court has jurisdiction to entertain this petition under {stat}.{rn}"
            )
        if case_type == "Property Dispute":
            return (
                f"1.\tThat the Plaintiff, {p}, is the lawful owner/tenant in settled possession of the property described in the schedule hereto, and is well conversant with the facts and circumstances of the present suit.\n\n"
                f"2.\tThat the Defendant, {r}, in respect of the said property, the following events transpired:\n\n{desc}\n\n"
                f"3.\tThat on or about {effective_inc}, the Defendant illegally interfered with/encroached upon/dispossessed the Plaintiff from the said property valued at {contract_amt}, without due process of law, and continues to threaten the Plaintiff’s peaceful possession.\n\n"
                f"4.\tThat the cause of action arose on the date of such illegal interference/dispossession and is continuing, and the suit property is situated within the jurisdiction of this Hon’ble Court.\n\n"
                f"5.\tThat this Hon’ble Court has full territorial and pecuniary jurisdiction to try and decide this suit under {stat}.{rn}"
            )
        # Civil (and any unrecognised case type) — generic civil suit narrative.
        return (
            f"1.\tThat the Plaintiff, {p}, through its Authorised Representative, is well conversant with the facts and circumstances of the present suit and is duly authorised to represent and sign the plaint before this Hon’ble Court.\n\n"
            f"2.\tThat the Defendant, {r}, was known to the Plaintiff, and the following events transpired between the parties:\n\n{desc}\n\n"
            f"3.\tThat the Defendant breached the terms agreed between the parties on or about {effective_inc}, causing loss and damages of {damages_amt if damages_amt != '[TO BE CONFIRMED: damages claimed]' else contract_amt} to the Plaintiff, who is entitled to recover the same along with interest.\n\n"
            f"4.\tThat the cause of action arose on the date of breach and continues, within the territorial and pecuniary jurisdiction of this Hon’ble Court.\n\n"
            f"5.\tThat this Hon’ble Court has full jurisdiction to try and decide this suit under {stat}, and the suit is filed within the period of limitation.{rn}"
        )

    def _prayer_text(self, case_type, p, r, relief, stat, fs=None, damages_claimed=None):
        """Prayer section with MISSING placeholders and review notes."""
        self._get_fs_field(fs, "damages_claimed", "damages claimed") if fs else "damages claimed"
        self._get_fs_field(fs, "contract_value", "contract value") if fs else "contract value"
        self._get_fs_field(fs, "place", "place") if fs else "place"
        ", ".join(fs.get("statutes_cited_by_user", [])) if fs else "applicable provisions of law"
        self._get_fs_field(fs, "claim_type", "claim type") if fs else "claim type"


        if case_type == "Criminal":
            return (
                f"\tIt is, therefore, most respectfully prayed that the Hon’ble Court may be pleased to take cognizance of this complaint and the Accused, {r}, may kindly be summoned, tried and punished for the offence committed u/s {stat} in accordance with law, in the interest of justice.\n\n"
                f"\t{relief}.\n\n"
                f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Complainant and against the Accused, in the interest of justice."
            )
        if case_type == "Family Law":
            return (
                f"\tIt is, therefore, most respectfully prayed that the Hon’ble Family Court may be pleased to grant the relief sought against the Respondent, {r}, in accordance with {stat}, in the interest of justice.\n\n"
                f"\t{relief}.\n\n"
                f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Petitioner, in the interest of justice."
            )
        if case_type == "Labour / Employment":
            return (
                f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court/Tribunal may be pleased to direct reinstatement of the Workman, {p}, with full back wages and continuity of service against the Management, {r}, under {stat}, in the interest of justice.\n\n"
                f"\t{relief}.\n\n"
                f"Any other or further order which this Hon’ble Court/Tribunal may deem fit and proper may also be passed in favour of the Workman, in the interest of justice."
            )
        if case_type == "Constitutional":
            return (
                f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court may be pleased to issue an appropriate writ, order, or direction quashing the impugned action of the Respondent, {r}, as being violative of {stat}, in the interest of justice.\n\n"
                f"\t{relief}.\n\n"
                f"Any other or further writ, order, or direction which this Hon’ble Court may deem fit and proper may also be passed in favour of the Petitioner, in the interest of justice."
            )
        if case_type == "Property Dispute":
            return (
                f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court may be pleased to decree the suit for possession and grant a permanent injunction restraining the Defendant, {r}, from interfering with the Plaintiff’s peaceful possession, under {stat}, in the interest of justice.\n\n"
                f"\t{relief}.\n\n"
                f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Plaintiff, in the interest of justice."
            )
        # Civil default - separate contract value and damages
        return (
            f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court may be pleased to decree the suit in favour of the Plaintiff and against the Defendant, {r}, for recovery of {damages_claimed} (damages claimed) and interest and costs under {stat}, in the interest of justice.\n\n"
            f"\t{relief}.\n\n"
            f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Plaintiff, in the interest of justice."
            f"[REVIEW NOTE: Contract value and damages are separate. Do not equate them. Damages must be separately pleaded.]"
            f"[REVIEW NOTE: Section 73 applies to damages only; specific performance is under SRA ss.10/14/16. Cite correct sections for each relief.]"
        )

    def _witnesses_for(self, case_type, p, fs=None):
        """Witness list - no defendant witnesses in plaintiff's list."""
        common_tail = ["Any other witness with the permission of this Hon’ble Court."]
        p_name = p  # exact name from FactSheet

        if case_type == "Criminal":
            return [
                f"Authorised Representative of the Complainant, {p_name}, who is well conversant with the facts and circumstances of the complaint.",
                "Clerk / Officer of the bank on which the cheque was drawn, with all relevant records.",
                "Clerk / Officer of the bank where the cheque was deposited for realisation, with all relevant records.",
                "Clerk / Officer of the concerned Post Office with relevant records.",
            ] + common_tail
        if case_type == "Family Law":
            return [
                f"The Petitioner, {p_name}, in person.",
                "Family members/relatives acquainted with the facts of the marriage and the conduct complained of.",
                "Marriage counsellor / mediator, if any was engaged.",
            ] + common_tail
        if case_type == "Labour / Employment":
            return [
                f"The Workman, {p_name}, in person.",
                "Co-workers/colleagues with knowledge of the circumstances of termination.",
                "Representative of the Trade Union, if applicable.",
                "Officer of the Management with custody of service/personnel records.",
            ] + common_tail
        if case_type == "Constitutional":
            return [
                f"The Petitioner, {p_name}, in person, on the basis of the accompanying affidavit.",
                "Officer of the Respondent authority with custody of the impugned order/records.",
            ] + common_tail
        if case_type == "Property Dispute":
            return [
                f"The Plaintiff, {p_name}, in person.",
                "Neighbours/local residents acquainted with possession of the suit property.",
                "Revenue/Municipal official with custody of land/property records.",
            ] + common_tail
        # Civil default - NO defendant witnesses in plaintiff's list
        return [
            f"Authorised Representative of the Plaintiff, {p_name}, who is well conversant with the facts and circumstances of the suit.",
            "Witness(es) to the transaction/agreement between the parties.",
            "Any expert witness, if required.",
        ] + common_tail

    def _documents_for(self, case_type, amt, inc, fs=None):
        """Documents list with MISSING placeholders. Statutes/case law NOT listed as exhibits."""
        self._get_fs_field(fs, "contract_value", "contract value") if fs else amt
        contract_date = self._get_fs_field(fs, "contract_date", "contract date") if fs else "contract date"
        contract_amt = self._get_fs_field(fs, "contract_value", "contract value") if fs else amt
        incident_date = self._get_fs_field(fs, "incident_date", "incident date") if fs else "incident date"

        if case_type == "Criminal":
            return [
                "Resolution / Authority letter authorising the AR",
                f"Copies of invoices / bills / ledger account showing dues of {contract_amt}",
                f"Original cheque for {contract_amt} dated {contract_date}",
                "Original cheque returning / dishonour memo from bank",
                "Copy of legal demand notice issued to the Accused",
                "Original postal receipt and Proof of Delivery (POD)",
                "Copy of email / electronic communication sent to the Accused",
                "Any other document as may be permitted by this Hon’ble Court",
            ]
        if case_type == "Family Law":
            return [
                "Marriage certificate / proof of marriage",
                "Photographs and correspondence evidencing the conduct complained of",
                "Income/salary documents of the parties, where relevant to maintenance",
                "Any prior complaint/FIR/medical record, if applicable",
                "Any other document as may be permitted by this Hon’ble Court",
            ]
        if case_type == "Labour / Employment":
            return [
                "Appointment letter / employment contract",
                f"Termination/dismissal order dated {incident_date}",
                "Salary slips and proof of wages last drawn",
                "Identity proof / employee ID",
                "Any other document as may be permitted by this Hon’ble Court/Tribunal",
            ]
        if case_type == "Constitutional":
            return [
                "Copy of the impugned order/action",
                "Representations made to the Respondent authority and replies, if any",
                "Identity/citizenship proof of the Petitioner",
                "Any other document as may be permitted by this Hon’ble Court",
            ]
        if case_type == "Property Dispute":
            return [
                "Sale deed / title documents of the suit property",
                "Mutation extract / revenue records",
                f"Property valuation of {contract_amt} and tax receipts",
                "Site plan of the suit property",
                "Any other document as may be permitted by this Hon’ble Court",
            ]
        # Civil default - statutes and case law are NOT exhibits
        return [
            "Agreement / contract between the parties",
            "Correspondence exchanged between the parties",
            f"Ledger account / invoices showing dues of {contract_amt}",
            "Copy of legal notice, if any was issued",
            "Any other document as may be permitted by this Hon’ble Court",
        ]

    def _affidavit_body(self, case_type, p, inc, amt, stat, fs=None):
        self._get_fs_field(fs, "contract_value", "contract value") if fs else amt
        incident_date = self._get_fs_field(fs, "incident_date", "incident date") if fs else "incident date"
        self._get_fs_field(fs, "contract_date", "contract date") if fs else "contract date"
        contract_amt = self._get_fs_field(fs, "contract_value", "contract value") if fs else "contract value"

        if case_type == "Criminal":
            return (
                f"1.\tThat the deponent is the Authorised Representative of the Complainant who has filed the above complaint with regard to the cheque dated {incident_date} for a sum of {contract_amt}.\n\n"
                f"2.\tThat the Complainant has not filed any other complaint/case regarding the dishonoring of the above said cheque in any other court except the present complaint. The contents of the accompanying complaint may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity."
            )
        if case_type == "Family Law":
            return (
                f"1.\tThat the deponent is the Petitioner who has filed the above petition under {stat}.\n\n"
                f"2.\tThat the deponent has not filed any other petition seeking the same relief in any other court except the present petition. The contents of the accompanying petition may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity."
            )
        if case_type == "Labour / Employment":
            return (
                f"1.\tThat the deponent is the Workman who has filed the above petition with regard to the termination dated {incident_date} under {stat}.\n\n"
                f"2.\tThat the deponent has not raised this industrial dispute in any other forum except the present proceedings. The contents of the accompanying petition may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity."
            )
        if case_type == "Constitutional":
            return (
                f"1.\tThat the deponent is the Petitioner who has filed the above writ petition in respect of the impugned action dated {incident_date} under {stat}.\n\n"
                f"2.\tThat the deponent has not filed any other petition seeking the same relief in any other court except the present petition. The contents of the accompanying petition may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity."
            )
        if case_type == "Property Dispute":
            return (
                f"1.\tThat the deponent is the Plaintiff who has filed the above suit with regard to the property and the dispossession/interference dated {incident_date} valued at {contract_amt}.\n\n"
                f"2.\tThat the deponent has not filed any other suit seeking the same relief in any other court except the present suit. The contents of the accompanying plaint may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity."
            )
        # Civil default
        return (
            f"1.\tThat the deponent is the Authorised Representative of the Plaintiff who has filed the above suit with regard to the breach dated {incident_date} and damages of {contract_amt}.\n\n"
            f"2.\tThat the Plaintiff has not filed any other suit seeking the same relief in any other court except the present suit. The contents of the accompanying plaint may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity."
        )

    def _evidence_body(self, case_type, sd, inc, amt, stat, fs=None):
        self._get_fs_field(fs, "contract_value", "contract value") if fs else "contract value"
        self._get_fs_field(fs, "contract_date", "contract date") if fs else "contract date"
        incident_date = self._get_fs_field(fs, "incident_date", "incident date") if fs else "incident date"
        contract_amt = self._get_fs_field(fs, "contract_value", "contract value") if fs else "contract value"
        self._get_fs_field(fs, "damages_claimed", "damages claimed") if fs else "damages claimed"
        self._get_fs_field(fs, "place", "place") if fs else "place"

        if case_type == "Criminal":
            return (
                f"1.\tI am well conversant with the facts and circumstances of the complaint and am duly authorised to represent the firm before this Hon’ble Court. The Original resolution is exhibited as EX. CW-1/1.\n\n"
                f"2.\t{sd}\n\tThe copy of ledger account / invoices is exhibited as EX. CW-1/2.\n\n"
                f"3.\tThat the Accused issued a cheque dated {incident_date} for a sum of {contract_amt} in favour of the Complainant which was dishonoured. The original cheque is exhibited as EX. CW-1/3 and the dishonour memo is exhibited as EX. CW-1/4.\n\n"
                f"4.\tThat the legal demand notice was duly served upon the Accused who failed to pay within 15 days. Legal notice is exhibited as EX. CW-1/5. Postal receipt and POD is exhibited as EX. CW-1/6. Email copy is exhibited as EX. CW-1/7.\n\n"
                f"5.\tThat the Accused is liable to be prosecuted u/s {stat}. I hereby close my pre-summoning evidence. My statements are true and correct."
            )
        if case_type == "Family Law":
            return (
                f"1.\tI am well conversant with the facts and circumstances of the petition and the marriage between the parties.\n\n"
                f"2.\t{sd}\n\tThe copy of marriage certificate is exhibited as EX. PW-1/1.\n\n"
                f"3.\tThat the cruelty/desertion described above occurred on or about {incident_date}, rendering it impossible for me to continue to reside with the Respondent. Supporting photographs/correspondence are exhibited as EX. PW-1/2.\n\n"
                f"4.\tThat I am entitled to the relief sought under {stat}. I hereby close my evidence. My statements are true and correct."
            )
        if case_type == "Labour / Employment":
            return (
                f"1.\tI am well conversant with the facts and circumstances of the petition and the terms of my employment.\n\n"
                f"2.\t{sd}\n\tThe copy of appointment letter is exhibited as EX. WW-1/1.\n\n"
                f"3.\tThat my services were terminated on {incident_date} without notice or retrenchment compensation of {contract_amt}, in violation of {stat}. The termination order is exhibited as EX. WW-1/2.\n\n"
                f"4.\tThat I am entitled to reinstatement and back wages under {stat}. I hereby close my evidence. My statements are true and correct."
            )
        if case_type == "Constitutional":
            return (
                f"1.\tI am well conversant with the facts and circumstances of the writ petition.\n\n"
                f"2.\t{sd}\n\tThe copy of the impugned order is exhibited as EX. PW-1/1.\n\n"
                f"3.\tThat the impugned action dated {incident_date} violates {stat}, and I have exhausted the available remedies before approaching this Hon’ble Court. Supporting representations are exhibited as EX. PW-1/2.\n\n"
                f"4.\tThat I am entitled to the relief sought. I hereby close my evidence. My statements are true and correct."
            )
        if case_type == "Property Dispute":
            return (
                f"1.\tI am well conversant with the facts and circumstances of the suit and my title/possession over the suit property.\n\n"
                f"2.\t{sd}\n\tThe copy of title documents is exhibited as EX. PW-1/1.\n\n"
                f"3.\tThat the Defendant illegally interfered with/dispossessed me from the suit property valued at {contract_amt} on or about {incident_date}. Supporting revenue records are exhibited as EX. PW-1/2.\n\n"
                f"4.\tThat I am entitled to possession and injunction under {stat}. I hereby close my evidence. My statements are true and correct."
            )
        # Civil default - separate contract value and damages
        return (
            f"1.\tI am well conversant with the facts and circumstances of the suit and am duly authorised to represent the Plaintiff before this Hon’ble Court.\n\n"
            f"2.\t{sd}\n\tThe copy of agreement / ledger account is exhibited as EX. CW-1/1.\n\n"
            f"3.\tThat the Defendant breached the agreement on or about {incident_date}, causing damages of {self._get_fs_field(fs, 'damages_claimed', 'damages claimed')} to the Plaintiff. Supporting correspondence is exhibited as EX. CW-1/2.\n\n"
            f"4.\tThat the Plaintiff is entitled to recover the said damages under {stat}. I hereby close my evidence. My statements are true and correct."
        )

    def _get_fs_field(self, fs: Optional[Dict], field_name: str, default: str = "") -> str:
        """Get a field value from FactSheet dict, returning placeholder if MISSING."""
        if fs and isinstance(fs, dict):
            field = fs.get(field_name, {})
            if field and field.get("value"):
                return field["value"]
            # Return placeholder for MISSING
            return missing_marker(field_name.replace("_", " "))
        return default or missing_marker(field_name.replace("_", " "))

    def _get_fs_field_dict(self, fs: Optional[Dict], field_name: str) -> Dict:
        """Get the full field dict from FactSheet."""
        if fs and isinstance(fs, dict):
            return fs.get(field_name, {})
        return {}

    def _prepare_context(self, ctx: Dict) -> Dict:
        """Classification gate: validate the case type BEFORE generating (works on a copy)."""
        ctx = dict(ctx)
        ctx["case_type"] = self.check_case_type(ctx)
        return ctx

    def _generate_ai(
        self, section: str, ctx: Dict, retries: int = 0
    ) -> Optional[SectionResult]:
        """AI-written text for a section: cloud provider chain first, then the local GGUF model.

        Returns None when no model produced text (the caller decides whether a template is acceptable).
        """
        result = self._generate_with_cloud(section, ctx, retries=retries)
        if result:
            return result
        if settings.ENABLE_LOCAL_LLM and self._ensure_local_llm():
            text = self._generate_with_llm(section, ctx)
            if text:
                return text, "local-llm"
        return None

    def _generate_section_with_source(self, section: str, ctx: Dict) -> SectionResult:
        """Cloud LLM -> local GGUF -> hardcoded template, reporting which one produced the text."""
        ctx = self._prepare_context(ctx)
        result = self._generate_ai(section, ctx)
        if result:
            return result
        return self._template_section(section, ctx), "template"

    def _t(self, section, ctx):
        return self._generate_section_with_source(section, ctx)[0]

    def _template_section(self, section: str, ctx: Dict) -> str:
        """Hardcoded, case-type-specific template (no model involved). Uses FactSheet with MISSING placeholders."""
        case_type = ctx.get("case_type", DEFAULT_CASE_TYPE)
        cfg = CASE_TYPE_CONFIG.get(case_type, CASE_TYPE_CONFIG[DEFAULT_CASE_TYPE])

        # Prefer FactSheet when available
        fs = ctx.get("fact_sheet") if isinstance(ctx.get("fact_sheet"), dict) else None
        ctx.get("raw_prompt", "")

        if fs:
            parties = fs.get("parties", [])
            p = parties[0].get("name") if parties else self._get_fs_field(fs, "contract_value", "Petitioner")
            r = parties[1].get("name") if len(parties) > 1 else self._get_fs_field(fs, "contract_value", "Respondent")
            court = ctx.get("court", "HON'BLE COURT")
            loc = ctx.get("location", "Delhi")
            desc = ctx.get("description", "")

            # Relief sought as list
            relief_items = fs.get("relief_sought", [])
            relief_text = "; ".join([r.get("value") for r in relief_items if r.get("value")]) if relief_items else ""

            # Statutes
            statutes = fs.get("statutes_cited_by_user", [])
            stat = ", ".join(statutes) if statutes else "applicable provisions of law"

            # Contract/incident dates
            contract_date = fs.get("contract_date", {}).get("value")
            incident_date = fs.get("incident_date", {}).get("value") or fs.get("contract_date", {}).get("value")

            # Money
            contract_value = fs.get("contract_value", {}).get("value")
            damages_claimed = fs.get("damages_claimed", {}).get("value")

            # Claim type
            fs.get("claim_type", {}).get("value", "")
            fs.get("claim_type_raw", {}).get("value", "")

            # Place
            fs.get("place", {}).get("value")

            # Court
            court = ctx.get("court", "HON'BLE COURT")

            # Description
            desc = ctx.get("description", "")

            # Relief sought
            relief = relief_text

            # Contract date
            inc = contract_date or incident_date or self._get_fs_field(fs, "contract_date", "contract date")

            # Statutes
            sl = statutes
            stat = ", ".join(sl) if sl else "applicable provisions of law"

            # Money
            contract_val = contract_value

            # Amt for backwards compat (use contract_value for complaint, damages for prayer)
            amt = contract_val

            # Year
            yr = datetime.datetime.now().year

            # RAG
            rag = ctx.get("rag_context", "")

            # Review notes
            review_note_parties = "\n[REVIEW NOTE: Exact legal names and entity types to be confirmed.]"
            review_note_roles = "\n[REVIEW NOTE: Party roles assumed from the prompt; confirm which party you represent.]"
            review_note_statutes = "\n[REVIEW NOTE: Section 73 applies to damages only; specific performance is under SRA ss.10/14/16.]"

            sig = (
                f"\t\t\t\t\t\t\t\t\t{cfg['p_label'].upper()}\n{loc}\t\t\t\t\t\t\tThrough\n"
                f"Dated: ___________\t\t\t\t\t\t\t\tCounsel"
            )

            # Party labels from case type config
            cfg['p_label']
            cfg['r_label']

            # Use exact party names from FactSheet (no suffixes)
            p = parties[0].get("name") if parties else self._get_fs_field(fs, "contract_value", "Petitioner")
            r = parties[1].get("name") if len(parties) > 1 else self._get_fs_field(fs, "contract_value", "Respondent")

            # Use exact party names (no suffixes added)
        else:
            # Legacy fallback
            p = ctx.get("petitioner", "Petitioner")
            r = ctx.get("respondent", "Respondent")
            court = ctx.get("court", "HON'BLE COURT")
            loc = ctx.get("location", "Delhi")
            desc = ctx.get("description", "")
            relief = ctx.get("relief_sought", "appropriate relief as deemed fit")
            inc = ctx.get("incident_date", "the relevant date")
            sl = ctx.get("statutes", [])
            stat = ", ".join(sl) if sl else "applicable provisions of law"
            ml = ctx.get("money", [])
            amt = ml[0] if ml else "the due amount"
            yr = datetime.datetime.now().year
            rag = ctx.get("rag_context", "")
            rn = (
                "\n\n[Note: Draft prepared with reference to similar legal precedents via RAG.]"
                if rag
                else ""
            )
            sig = (
                f"\t\t\t\t\t\t\t\t\t{cfg['p_label'].upper()}\n{loc}\t\t\t\t\t\t\tThrough\n"
                f"Dated: ___________\t\t\t\t\t\t\t\tCounsel"
            )
            review_note_parties = ""
            review_note_roles = ""
            review_note_statutes = ""
            cfg['p_label']
            cfg['r_label']

        # MISSING placeholders
        self._get_fs_field(fs, "contract_date", "contract date") if fs else "[TO BE CONFIRMED: contract date]"
        self._get_fs_field(fs, "delivery_date", "delivery date") if fs else "[TO BE CONFIRMED: delivery date]"
        self._get_fs_field(fs, "incident_date", "incident date") if fs else "[TO BE CONFIRMED: incident date]"
        self._get_fs_field(fs, "contract_value", "contract value") if fs else "[TO BE CONFIRMED: contract value]"
        self._get_fs_field(fs, "damages_claimed", "damages claimed") if fs else "[TO BE CONFIRMED: damages claimed]"
        self._get_fs_field(fs, "place", "place") if fs else "[TO BE CONFIRMED: place]"
        self._get_fs_field(fs, "claim_type", "claim type") if fs else "[TO BE CONFIRMED: claim type]"
        self._get_fs_field(fs, "relief_sought", "relief sought") if fs else "[TO BE CONFIRMED: relief sought]"
        self._get_fs_field(fs, "has_arbitration_clause", "arbitration clause") if fs else "[TO BE CONFIRMED: arbitration clause]"

        if section == "title_block":
            ps_line = f"\t\t\t\t\t\t\t\t\t\tP.S.- {loc}\n\n" if cfg["show_ps"] else ""
            return (
                f"{self._court_header(court, loc, cfg, yr)}"
                f"IN THE MATTER OF:\n\n{p}\nThrough its Authorised Representative\n"
                f"\t\t\t\t\t\t\t……………………………………{cfg['p_label']}\n\n"
                f"\t\t\t\tVersus\n\n{r}\n"
                f"\t\t\t\t\t\t\t……………………………………………{cfg['r_label']}\n\n"
                f"{ps_line}"
                f"{cfg['doc_title'].format(stat=stat, amt=amt)}"
            )

        if section == "complaint_body":
            return f"MOST RESPECTFULLY SHOWETH:\n\n{self._narrative_paragraphs(case_type, p, r, desc, inc, amt, stat, rn, fs, review_note_parties, review_note_roles)}{review_note_parties}{review_note_roles}"

        if section == "prayer":
            return f"PRAYER\n\n{self._prayer_text(case_type, p, r, relief, stat, fs, damages_claimed)}{review_note_statutes}\n\n\n{sig}"

        if section == "list_of_witnesses":
            witnesses = self._witnesses_for(case_type, p, fs)
            body = "\n\n".join(f"{i}.\t{w}" for i, w in enumerate(witnesses, 1))
            return (
                f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                f"LIST OF WITNESSES\n\n{body}{review_note_parties}\n\n\n{sig}"
            )

        if section == "list_of_documents":
            documents = self._documents_for(case_type, amt, inc, fs)
            annexures = [chr(ord("A") + i) for i in range(len(documents))]
            body = "\n\n".join(
                f"{i}.\t{d}\t\t\t\t[Annexure – {a}]"
                for i, (d, a) in enumerate(zip(documents, annexures), 1)
            )
            return (
                f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                f"LIST OF DOCUMENTS\n\nSr. No.\tDescription of Document\t\t\t\t\t\tAnnexure\n\n{body}{review_note_parties}\n\n\n{sig}"
            )

        if section == "affidavit":
            return (
                f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                f"AFFIDAVIT\n\n"
                f"I, the deponent, {cfg['p_label']} herein / Authorised Representative of {p}, having its office at {loc}, do hereby solemnly affirm and declare as under:\n\n"
                f"{self._affidavit_body(case_type, p, inc, amt, stat, fs)}{review_note_parties}\n\n\n"
                f"Deponent\n\n\n"
                f"VERIFICATION:\n\n"
                f"Verified at {loc} on this _____ day of _____________ {yr}, that the contents of the above affidavit are true and correct to my knowledge and no part of it is false and nothing material has been concealed therefrom.\n\n\n"
                f"Deponent"
            )

        if section == "evidence_affidavit":
            sd = desc[:500] + "..." if len(desc) > 500 else desc
            return (
                f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                f"EVIDENCE BY WAY OF AFFIDAVIT\n\n"
                f"I, the deponent, {cfg['p_label']} herein / Authorised Representative of {p}, having its office at {loc}, do hereby solemnly affirm and declare as under:\n\n"
                f"{self._evidence_body(case_type, sd, inc, amt, stat, fs)}{review_note_parties}\n\n\n"
                f"Deponent\n\n\n"
                f"VERIFICATION:\n\n"
                f"Verified at {loc} on this _____ day of _____________ {yr} that the contents of the above affidavit are true to my knowledge and no part of it is false and nothing material has been concealed therefrom.\n\n\n"
                f"Deponent"
            )

        return "Section content not available."

    def generate_section(self, section, context):
        """Blocking: call from a worker thread (asyncio.to_thread)."""
        return self._t(section, context)

    async def generate_all_sections(self, context, strict: bool = False):
        """Generate all 7 draft sections.

        strict=False (default, used by the form flow): cloud LLM -> local
            GGUF -> hardcoded templates. A draft is always produced.
        strict=True (used by the AI-chat flow): AI models ONLY (cloud LLM, then
            the local GGUF model). If none of them can write a section, raise
            RuntimeError instead of silently serving a template - the caller
            marks the case 'failed' and the chat tells the user honestly.

        The returned dict holds the 7 section texts plus three bookkeeping keys that
        callers must pop before storing the sections: ``_generation_time``,
        ``_full_text`` and ``_model_used`` (what really wrote the text).

        Every blocking step (HTTP calls, local inference) runs in a worker thread so the
        event loop - and with it every other request - stays responsive.
        """
        start = time.time()
        ctx = self._prepare_context(context)
        sections: Dict[str, str] = {}
        sources: List[str] = []
        last_index = len(SECTION_ORDER) - 1

        for index, name in enumerate(SECTION_ORDER):
            if strict:
                # A short retry here: one transient 429/503 should not discard a whole draft.
                result = await asyncio.to_thread(self._generate_ai, name, ctx, 2)
                if not result:
                    raise RuntimeError(
                        f"Language model failed to generate the '{name}' section. "
                        "No draft was produced."
                    )
            else:
                result = await asyncio.to_thread(
                    self._generate_section_with_source, name, ctx
                )

            text, source = result
            sections[name] = text
            if source not in sources:
                sources.append(source)

            # Stagger remote calls so free-tier per-minute limits are not hit.
            called_remote_model = source not in ("template", "local-llm")
            if (
                called_remote_model
                and index < last_index
                and settings.LLM_SECTION_DELAY_SECONDS > 0
            ):
                await asyncio.sleep(settings.LLM_SECTION_DELAY_SECONDS)

        sections["_generation_time"] = round(time.time() - start, 2)
        sections["_full_text"] = ("\n\n" + "=" * 70 + "\n\n").join(
            sections[name] for name in SECTION_ORDER
        )
        sections["_model_used"] = "+".join(sources) if sources else "template"
        logger.info(
            f"All {len(SECTION_ORDER)} sections generated in {sections['_generation_time']}s "
            f"({sections['_model_used']})"
        )
        return sections

    # ---- Backwards-compat shims (older code probed these attrs) ----
    @property
    def use_groq(self) -> bool:
        return bool(self._provider == "groq" and self.client and self.client.available)

    @property
    def use_hf(self) -> bool:
        return bool(self._provider == "hf" and self.client and self.client.available)

    @property
    def _effective_provider(self) -> str:
        if self._provider and self.client and self.client.available:
            return self._provider
        if self.use_model:
            return "local"
        return "template"

    @property
    def model_label(self) -> str:
        if self.client and self.client.available:
            return f"{self._provider}:{self.client.model}"
        if self.use_model:
            return "local-llm"
        return "template"