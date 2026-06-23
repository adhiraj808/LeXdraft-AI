import logging, time, datetime, os
from typing import Dict
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False
    logger.warning("llama-cpp-python not installed. GGUF model will not be used.")


# Per-case-type pleading configuration used by the template fallback (when no
# GGUF model is loaded). Each case type gets its own party labels, case number
# prefix, and substantive narrative — without this, every case type produced
# the same NI Act cheque-dishonour criminal complaint text regardless of what
# the classifier actually determined the case to be.
CASE_TYPE_CONFIG = {
    "Criminal": {
        "p_label": "Complainant", "r_label": "Accused", "case_no_label": "C.C. NO.",
        "show_ps": True,
        "doc_title": "COMPLAINT ON BEHALF OF COMPLAINANT U/S {stat}",
    },
    "Civil": {
        "p_label": "Plaintiff", "r_label": "Defendant", "case_no_label": "C.S. NO.",
        "show_ps": False,
        "doc_title": "CIVIL SUIT FOR RECOVERY OF {amt} AND DAMAGES U/S {stat}",
    },
    "Family Law": {
        "p_label": "Petitioner", "r_label": "Respondent", "case_no_label": "H.M.A. PETITION NO.",
        "show_ps": False,
        "doc_title": "PETITION U/S {stat}",
    },
    "Labour / Employment": {
        "p_label": "Workman", "r_label": "Management", "case_no_label": "I.D. CASE NO.",
        "show_ps": False,
        "doc_title": "PETITION FOR REINSTATEMENT AND BACK WAGES U/S {stat}",
    },
    "Constitutional": {
        "p_label": "Petitioner", "r_label": "Respondent", "case_no_label": "W.P. NO.",
        "show_ps": False,
        "doc_title": "WRIT PETITION UNDER {stat}",
    },
    "Property Dispute": {
        "p_label": "Plaintiff", "r_label": "Defendant", "case_no_label": "C.S. NO.",
        "show_ps": False,
        "doc_title": "SUIT FOR POSSESSION AND PERMANENT INJUNCTION U/S {stat}",
    },
}

DEFAULT_CASE_TYPE = "Civil"


class LegalDraftGenerator:
    def __init__(self):
        self.use_model = False
        self.llm = None

    async def load(self):
        if not LLAMA_AVAILABLE:
            logger.error("Cannot load GGUF model: llama-cpp-python not available.")
            return

        model_path = settings.GGUF_MODEL_PATH
        if not os.path.exists(model_path):
            logger.error(f"GGUF model not found at {model_path}. Please run download script.")
            return

        try:
            logger.info(f"Loading GGUF model from {model_path}...")
            # n_gpu_layers=-1 if settings.USE_GPU else 0
            self.llm = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=os.cpu_count(),
                verbose=False
            )
            self.use_model = True
            logger.info("GGUF Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load GGUF model: {str(e)}")

    def _generate_with_llm(self, section, ctx):
        case_type = ctx.get("case_type", DEFAULT_CASE_TYPE)
        p       = ctx.get("petitioner","The Petitioner")
        r       = ctx.get("respondent","The Respondent")
        court   = ctx.get("court","HON'BLE COURT")
        loc     = ctx.get("location","Delhi")
        desc    = ctx.get("description","")
        relief  = ctx.get("relief_sought","")
        sl      = ctx.get("statutes",[])
        stat    = ", ".join(sl) if sl else "applicable provisions of law"
        rag     = ctx.get("rag_context","")

        prompt = f"""<|system|>
You are an expert Indian Legal Draftsman. Draft a professional {section.replace('_', ' ')} for a {case_type} case in India.
Follow the standard legal format and terminology used in Indian Courts for this case type.
Use the provided context to fill in details.
Context:
- Case Type: {case_type}
- Petitioner: {p}
- Respondent: {r}
- Court: {court}
- Location: {loc}
- Description: {desc}
- Relief Sought: {relief}
- Statutes: {stat}
- Additional RAG Context: {rag}

Draft the {section.replace('_', ' ')} section only.
<|assistant|>
"""
        try:
            output = self.llm(
                prompt,
                max_tokens=1024,
                stop=["<|end|>", "</s>"],
                temperature=0.7,
                top_p=0.9
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            return None

    def _parties_block(self, cfg, p, r):
        """Shared 'IN THE MATTER OF ... Versus ...' block used by most sections."""
        return (f"IN THE MATTER OF:\n\n{p}\n\t\t\t\t……………………………………{cfg['p_label']}\n\n"
                f"Versus\n\n{r}\n\t\t\t\t……………………………………………{cfg['r_label']}\n\n")

    def _court_header(self, court, loc, cfg, yr):
        return f"IN THE COURT OF {court.upper()}\n{loc.upper()} COURTS\n\n{cfg['case_no_label']} …………..{yr}\n\n"

    def _narrative_paragraphs(self, case_type, p, r, desc, inc, amt, stat, rn):
        """Case-type-specific cause-of-action narrative for the main pleading body."""
        if case_type == "Criminal":
            return (
                f"1.\tThat the Complainant, {p}, through its Authorised Representative, is well conversant with the facts and circumstances of the present complaint and is duly authorised to represent and sign this complaint before this Hon’ble Court.\n\n"
                f"2.\tThat the Complainant is a reputed firm/individual engaged in lawful business. The Accused, {r}, was known to the Complainant and the following events transpired between the parties:\n\n{desc}\n\n"
                f"3.\tThat the Accused issued a cheque/instrument dated {inc} for a sum of {amt} in favour of the Complainant to discharge their lawful liability. The said instrument was duly presented for realisation but was returned/dishonoured. The original cheque is annexed as Annexure C and the cheque returning memo is annexed as Annexure D.\n\n"
                f"4.\tThat the Complainant caused a legal demand notice to be served upon the Accused. The Accused failed to pay within the stipulated 15 days. The copy of legal notice is annexed as Annexure E. The postal receipt and POD is annexed as Annexure F. The copy of email is annexed as Annexure G.\n\n"
                f"5.\tThat the Accused is liable to be prosecuted u/s {stat}. The cause of action arose on each date of transaction, on dishonour of the cheque, and on failure to comply with the legal notice, all within the jurisdiction of this Hon’ble Court.\n\n"
                f"6.\tThat this Hon’ble Court has full territorial and pecuniary jurisdiction to try and decide this complaint. The complaint is filed within the period of limitation under {stat}.{rn}"
            )
        if case_type == "Family Law":
            return (
                f"1.\tThat the Petitioner, {p}, is the lawfully wedded spouse of the Respondent, {r}, and is well conversant with the facts and circumstances of the present petition.\n\n"
                f"2.\tThat the marriage between the parties was solemnised according to law, and the following events transpired during the subsistence of the marriage:\n\n{desc}\n\n"
                f"3.\tThat the conduct of the Respondent, more particularly described above, amounts to cruelty/desertion within the meaning of {stat}, rendering it impossible for the Petitioner to continue to reside with the Respondent.\n\n"
                f"4.\tThat the cause of action arose on {inc} and has continued since, within the territorial jurisdiction of this Hon’ble Court, where the parties last resided together / where the marriage was solemnised.\n\n"
                f"5.\tThat this Hon’ble Family Court has full jurisdiction to try and decide this petition under {stat}, and the petition is filed within the period of limitation, if any.{rn}"
            )
        if case_type == "Labour / Employment":
            return (
                f"1.\tThat the Workman, {p}, was employed by the Management, {r}, and is well conversant with the facts and circumstances of the present petition.\n\n"
                f"2.\tThat during the course of employment, the following events transpired leading to the present industrial dispute:\n\n{desc}\n\n"
                f"3.\tThat the termination/dismissal of the Workman effected by the Management on {inc} was done without following the mandatory procedure, notice, and retrenchment compensation of {amt} required under {stat}, and is therefore illegal and void ab initio.\n\n"
                f"4.\tThat the cause of action arose on the date of termination and continues, within the jurisdiction of this Hon’ble Labour Court/Industrial Tribunal.\n\n"
                f"5.\tThat this Hon’ble Court/Tribunal has full jurisdiction to adjudicate this dispute under {stat}.{rn}"
            )
        if case_type == "Constitutional":
            return (
                f"1.\tThat the Petitioner, {p}, is a citizen of India whose fundamental/legal rights have been violated by the action of the Respondent, {r}, a State/statutory authority within the meaning of Article 12 of the Constitution.\n\n"
                f"2.\tThat the facts giving rise to the violation are as under:\n\n{desc}\n\n"
                f"3.\tThat the impugned action/order dated {inc} is in violation of {stat} and is liable to be quashed/set aside as being arbitrary, unconstitutional, and without authority of law.\n\n"
                f"4.\tThat the Petitioner has no other equally efficacious remedy except to approach this Hon’ble Court by way of this writ petition, and the cause of action arose within the jurisdiction of this Hon’ble Court.\n\n"
                f"5.\tThat this Hon’ble Court has jurisdiction to entertain this petition under {stat}.{rn}"
            )
        if case_type == "Property Dispute":
            return (
                f"1.\tThat the Plaintiff, {p}, is the lawful owner/tenant in settled possession of the property described in the schedule hereto, and is well conversant with the facts and circumstances of the present suit.\n\n"
                f"2.\tThat the Defendant, {r}, in respect of the said property, the following events transpired:\n\n{desc}\n\n"
                f"3.\tThat on or about {inc}, the Defendant illegally interfered with/encroached upon/dispossessed the Plaintiff from the said property valued at {amt}, without due process of law, and continues to threaten the Plaintiff’s peaceful possession.\n\n"
                f"4.\tThat the cause of action arose on the date of such illegal interference/dispossession and is continuing, and the suit property is situated within the jurisdiction of this Hon’ble Court.\n\n"
                f"5.\tThat this Hon’ble Court has full territorial and pecuniary jurisdiction to try and decide this suit under {stat}.{rn}"
            )
        # Civil (and any unrecognised case type) — generic civil suit narrative.
        return (
            f"1.\tThat the Plaintiff, {p}, through its Authorised Representative, is well conversant with the facts and circumstances of the present suit and is duly authorised to represent and sign the plaint before this Hon’ble Court.\n\n"
            f"2.\tThat the Defendant, {r}, was known to the Plaintiff, and the following events transpired between the parties:\n\n{desc}\n\n"
            f"3.\tThat the Defendant breached the terms agreed between the parties on or about {inc}, causing loss and damages of {amt} to the Plaintiff, who is entitled to recover the same along with interest.\n\n"
            f"4.\tThat the cause of action arose on the date of breach and continues, within the territorial and pecuniary jurisdiction of this Hon’ble Court.\n\n"
            f"5.\tThat this Hon’ble Court has full jurisdiction to try and decide this suit under {stat}, and the suit is filed within the period of limitation.{rn}"
        )

    def _prayer_text(self, case_type, p, r, relief, stat):
        if case_type == "Criminal":
            return (f"\tIt is, therefore, most respectfully prayed that the Hon’ble Court may be pleased to take cognizance of this complaint and the Accused, {r}, may kindly be summoned, tried and punished for the offence committed u/s {stat} in accordance with law, in the interest of justice.\n\n"
                    f"\t{relief}.\n\n"
                    f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Complainant and against the Accused, in the interest of justice.")
        if case_type == "Family Law":
            return (f"\tIt is, therefore, most respectfully prayed that the Hon’ble Family Court may be pleased to grant the relief sought against the Respondent, {r}, in accordance with {stat}, in the interest of justice.\n\n"
                    f"\t{relief}.\n\n"
                    f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Petitioner, in the interest of justice.")
        if case_type == "Labour / Employment":
            return (f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court/Tribunal may be pleased to direct reinstatement of the Workman, {p}, with full back wages and continuity of service against the Management, {r}, under {stat}, in the interest of justice.\n\n"
                    f"\t{relief}.\n\n"
                    f"Any other or further order which this Hon’ble Court/Tribunal may deem fit and proper may also be passed in favour of the Workman, in the interest of justice.")
        if case_type == "Constitutional":
            return (f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court may be pleased to issue an appropriate writ, order, or direction quashing the impugned action of the Respondent, {r}, as being violative of {stat}, in the interest of justice.\n\n"
                    f"\t{relief}.\n\n"
                    f"Any other or further writ, order, or direction which this Hon’ble Court may deem fit and proper may also be passed in favour of the Petitioner, in the interest of justice.")
        if case_type == "Property Dispute":
            return (f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court may be pleased to decree the suit for possession and grant a permanent injunction restraining the Defendant, {r}, from interfering with the Plaintiff’s peaceful possession, under {stat}, in the interest of justice.\n\n"
                    f"\t{relief}.\n\n"
                    f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Plaintiff, in the interest of justice.")
        # Civil default
        return (f"\tIt is, therefore, most respectfully prayed that this Hon’ble Court may be pleased to decree the suit in favour of the Plaintiff and against the Defendant, {r}, for recovery of damages along with interest and costs under {stat}, in the interest of justice.\n\n"
                f"\t{relief}.\n\n"
                f"Any other or further order which this Hon’ble Court may deem fit and proper may also be passed in favour of the Plaintiff, in the interest of justice.")

    def _witnesses_for(self, case_type, p):
        common_tail = ["Any other witness with the permission of this Hon’ble Court."]
        if case_type == "Criminal":
            return [f"Authorised Representative of the Complainant, {p}, who is well conversant with the facts and circumstances of the complaint.",
                    "Clerk / Officer of the bank on which the cheque was drawn, with all relevant records.",
                    "Clerk / Officer of the bank where the cheque was deposited for realisation, with all relevant records.",
                    "Clerk / Officer of the concerned Post Office with relevant records."] + common_tail
        if case_type == "Family Law":
            return [f"The Petitioner, {p}, in person.",
                    "Family members/relatives acquainted with the facts of the marriage and the conduct complained of.",
                    "Marriage counsellor / mediator, if any was engaged."] + common_tail
        if case_type == "Labour / Employment":
            return [f"The Workman, {p}, in person.",
                    "Co-workers/colleagues with knowledge of the circumstances of termination.",
                    "Representative of the Trade Union, if applicable.",
                    "Officer of the Management with custody of service/personnel records."] + common_tail
        if case_type == "Constitutional":
            return [f"The Petitioner, {p}, in person, on the basis of the accompanying affidavit.",
                    "Officer of the Respondent authority with custody of the impugned order/records."] + common_tail
        if case_type == "Property Dispute":
            return [f"The Plaintiff, {p}, in person.",
                    "Neighbours/local residents acquainted with possession of the suit property.",
                    "Revenue/Municipal official with custody of land/property records."] + common_tail
        # Civil default
        return [f"Authorised Representative of the Plaintiff, {p}, who is well conversant with the facts and circumstances of the suit.",
                "Witness(es) to the transaction/agreement between the parties.",
                "Any expert witness, if required."] + common_tail

    def _documents_for(self, case_type, amt, inc):
        if case_type == "Criminal":
            return [
                "Resolution / Authority letter authorising the AR",
                f"Copies of invoices / bills / ledger account showing dues of {amt}",
                f"Original cheque for {amt} dated {inc}",
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
                f"Termination/dismissal order dated {inc}",
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
                f"Property valuation of {amt} and tax receipts",
                "Site plan of the suit property",
                "Any other document as may be permitted by this Hon’ble Court",
            ]
        # Civil default
        return [
            "Agreement / contract between the parties",
            "Correspondence exchanged between the parties",
            f"Ledger account / invoices showing dues of {amt}",
            "Copy of legal notice, if any was issued",
            "Any other document as may be permitted by this Hon’ble Court",
        ]

    def _affidavit_body(self, case_type, p, inc, amt, stat):
        if case_type == "Criminal":
            return (f"1.\tThat the deponent is the Authorised Representative of the Complainant who has filed the above complaint with regard to the cheque dated {inc} for a sum of {amt}.\n\n"
                    f"2.\tThat the Complainant has not filed any other complaint/case regarding the dishonoring of the above said cheque in any other court except the present complaint. The contents of the accompanying complaint may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity.")
        if case_type == "Family Law":
            return (f"1.\tThat the deponent is the Petitioner who has filed the above petition under {stat}.\n\n"
                    f"2.\tThat the deponent has not filed any other petition seeking the same relief in any other court except the present petition. The contents of the accompanying petition may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity.")
        if case_type == "Labour / Employment":
            return (f"1.\tThat the deponent is the Workman who has filed the above petition with regard to the termination dated {inc} under {stat}.\n\n"
                    f"2.\tThat the deponent has not raised this industrial dispute in any other forum except the present proceedings. The contents of the accompanying petition may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity.")
        if case_type == "Constitutional":
            return (f"1.\tThat the deponent is the Petitioner who has filed the above writ petition in respect of the impugned action dated {inc} under {stat}.\n\n"
                    f"2.\tThat the deponent has not filed any other petition seeking the same relief in any other court except the present petition. The contents of the accompanying petition may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity.")
        if case_type == "Property Dispute":
            return (f"1.\tThat the deponent is the Plaintiff who has filed the above suit with regard to the property and the dispossession/interference dated {inc} valued at {amt}.\n\n"
                    f"2.\tThat the deponent has not filed any other suit seeking the same relief in any other court except the present suit. The contents of the accompanying plaint may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity.")
        # Civil default
        return (f"1.\tThat the deponent is the Authorised Representative of the Plaintiff who has filed the above suit with regard to the breach dated {inc} and damages of {amt}.\n\n"
                f"2.\tThat the Plaintiff has not filed any other suit seeking the same relief in any other court except the present suit. The contents of the accompanying plaint may kindly be read as part and parcel of this affidavit as the same are not being repeated herein for the sake of brevity.")

    def _evidence_body(self, case_type, sd, inc, amt, stat):
        if case_type == "Criminal":
            return (f"1.\tI am well conversant with the facts and circumstances of the complaint and am duly authorised to represent the firm before this Hon’ble Court. The Original resolution is exhibited as EX. CW-1/1.\n\n"
                    f"2.\t{sd}\n\tThe copy of ledger account / invoices is exhibited as EX. CW-1/2.\n\n"
                    f"3.\tThat the Accused issued a cheque dated {inc} for a sum of {amt} in favour of the Complainant which was dishonoured. The original cheque is exhibited as EX. CW-1/3 and the dishonour memo is exhibited as EX. CW-1/4.\n\n"
                    f"4.\tThat the legal demand notice was duly served upon the Accused who failed to pay within 15 days. Legal notice is exhibited as EX. CW-1/5. Postal receipt and POD is exhibited as EX. CW-1/6. Email copy is exhibited as EX. CW-1/7.\n\n"
                    f"5.\tThat the Accused is liable to be prosecuted u/s {stat}. I hereby close my pre-summoning evidence. My statements are true and correct.")
        if case_type == "Family Law":
            return (f"1.\tI am well conversant with the facts and circumstances of the petition and the marriage between the parties.\n\n"
                    f"2.\t{sd}\n\tThe copy of marriage certificate is exhibited as EX. PW-1/1.\n\n"
                    f"3.\tThat the cruelty/desertion described above occurred on or about {inc}, rendering it impossible for me to continue to reside with the Respondent. Supporting photographs/correspondence are exhibited as EX. PW-1/2.\n\n"
                    f"4.\tThat I am entitled to the relief sought under {stat}. I hereby close my evidence. My statements are true and correct.")
        if case_type == "Labour / Employment":
            return (f"1.\tI am well conversant with the facts and circumstances of the petition and the terms of my employment.\n\n"
                    f"2.\t{sd}\n\tThe copy of appointment letter is exhibited as EX. WW-1/1.\n\n"
                    f"3.\tThat my services were terminated on {inc} without notice or retrenchment compensation of {amt}, in violation of {stat}. The termination order is exhibited as EX. WW-1/2.\n\n"
                    f"4.\tThat I am entitled to reinstatement and back wages under {stat}. I hereby close my evidence. My statements are true and correct.")
        if case_type == "Constitutional":
            return (f"1.\tI am well conversant with the facts and circumstances of the writ petition.\n\n"
                    f"2.\t{sd}\n\tThe copy of the impugned order is exhibited as EX. PW-1/1.\n\n"
                    f"3.\tThat the impugned action dated {inc} violates {stat}, and I have exhausted the available remedies before approaching this Hon’ble Court. Supporting representations are exhibited as EX. PW-1/2.\n\n"
                    f"4.\tThat I am entitled to the relief sought. I hereby close my evidence. My statements are true and correct.")
        if case_type == "Property Dispute":
            return (f"1.\tI am well conversant with the facts and circumstances of the suit and my title/possession over the suit property.\n\n"
                    f"2.\t{sd}\n\tThe copy of title documents is exhibited as EX. PW-1/1.\n\n"
                    f"3.\tThat the Defendant illegally interfered with/dispossessed me from the suit property valued at {amt} on or about {inc}. Supporting revenue records are exhibited as EX. PW-1/2.\n\n"
                    f"4.\tThat I am entitled to possession and injunction under {stat}. I hereby close my evidence. My statements are true and correct.")
        # Civil default
        return (f"1.\tI am well conversant with the facts and circumstances of the suit and am duly authorised to represent the Plaintiff before this Hon’ble Court.\n\n"
                f"2.\t{sd}\n\tThe copy of agreement / ledger account is exhibited as EX. CW-1/1.\n\n"
                f"3.\tThat the Defendant breached the agreement on or about {inc}, causing damages of {amt} to the Plaintiff. Supporting correspondence is exhibited as EX. CW-1/2.\n\n"
                f"4.\tThat the Plaintiff is entitled to recover the said damages under {stat}. I hereby close my evidence. My statements are true and correct.")

    def _t(self, section, ctx):
        if self.use_model and self.llm:
            llm_text = self._generate_with_llm(section, ctx)
            if llm_text:
                return llm_text

        # Fallback to hardcoded, case-type-specific templates.
        case_type = ctx.get("case_type", DEFAULT_CASE_TYPE)
        cfg     = CASE_TYPE_CONFIG.get(case_type, CASE_TYPE_CONFIG[DEFAULT_CASE_TYPE])
        p       = ctx.get("petitioner", f"The {cfg['p_label']}")
        r       = ctx.get("respondent", f"The {cfg['r_label']}")
        court   = ctx.get("court","HON'BLE COURT")
        loc     = ctx.get("location","Delhi")
        desc    = ctx.get("description","")
        relief  = ctx.get("relief_sought","appropriate relief as deemed fit by this Hon'ble Court")
        inc     = ctx.get("incident_date","the relevant date")
        sl      = ctx.get("statutes",[])
        stat    = ", ".join(sl) if sl else "applicable provisions of law"
        ml      = ctx.get("money",[])
        amt     = ml[0] if ml else "the due amount"
        yr      = datetime.datetime.now().year
        rag     = ctx.get("rag_context","")
        rn      = "\n\n[Note: Draft prepared with reference to similar legal precedents via RAG.]" if rag else ""
        sig     = (f"\t\t\t\t\t\t\t\t\t{cfg['p_label'].upper()}\n{loc}\t\t\t\t\t\t\tThrough\n"
                   f"Dated: ___________\t\t\t\t\t\t\t\tCounsel")

        if section == "title_block":
            ps_line = f"\t\t\t\t\t\t\t\t\t\tP.S.- {loc}\n\n" if cfg["show_ps"] else ""
            return (f"{self._court_header(court, loc, cfg, yr)}"
                    f"IN THE MATTER OF:\n\n{p}\nThrough its Authorised Representative\n"
                    f"\t\t\t\t\t\t\t……………………………………{cfg['p_label']}\n\n"
                    f"\t\t\t\tVersus\n\n{r}\n"
                    f"\t\t\t\t\t\t\t……………………………………………{cfg['r_label']}\n\n"
                    f"{ps_line}"
                    f"{cfg['doc_title'].format(stat=stat, amt=amt)}")

        if section == "complaint_body":
            return f"MOST RESPECTFULLY SHOWETH:\n\n{self._narrative_paragraphs(case_type, p, r, desc, inc, amt, stat, rn)}"

        if section == "prayer":
            return f"PRAYER\n\n{self._prayer_text(case_type, p, r, relief, stat)}\n\n\n{sig}"

        if section == "list_of_witnesses":
            witnesses = self._witnesses_for(case_type, p)
            body = "\n\n".join(f"{i}.\t{w}" for i, w in enumerate(witnesses, 1))
            return (f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                    f"LIST OF WITNESSES\n\n{body}\n\n\n{sig}")

        if section == "list_of_documents":
            documents = self._documents_for(case_type, amt, inc)
            annexures = [chr(ord("A") + i) for i in range(len(documents))]
            body = "\n\n".join(f"{i}.\t{d}\t\t\t\t[Annexure – {a}]" for i, (d, a) in enumerate(zip(documents, annexures), 1))
            return (f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                    f"LIST OF DOCUMENTS\n\nSr. No.\tDescription of Document\t\t\t\t\t\tAnnexure\n\n{body}\n\n\n{sig}")

        if section == "affidavit":
            return (f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                    f"AFFIDAVIT\n\n"
                    f"I, the deponent, {cfg['p_label']} herein / Authorised Representative of {p}, having its office at {loc}, do hereby solemnly affirm and declare as under:\n\n"
                    f"{self._affidavit_body(case_type, p, inc, amt, stat)}\n\n\n"
                    f"Deponent\n\n\n"
                    f"VERIFICATION:\n\n"
                    f"Verified at {loc} on this _____ day of _____________ {yr}, that the contents of the above affidavit are true and correct to my knowledge and no part of it is false and nothing material has been concealed therefrom.\n\n\n"
                    f"Deponent")

        if section == "evidence_affidavit":
            sd = desc[:500] + "..." if len(desc) > 500 else desc
            return (f"{self._court_header(court, loc, cfg, yr)}{self._parties_block(cfg, p, r)}"
                    f"EVIDENCE BY WAY OF AFFIDAVIT\n\n"
                    f"I, the deponent, {cfg['p_label']} herein / Authorised Representative of {p}, having its office at {loc}, do hereby solemnly affirm and declare as under:\n\n"
                    f"{self._evidence_body(case_type, sd, inc, amt, stat)}\n\n\n"
                    f"Deponent\n\n\n"
                    f"VERIFICATION:\n\n"
                    f"Verified at {loc} on this _____ day of _____________ {yr} that the contents of the above affidavit are true to my knowledge and no part of it is false and nothing material has been concealed therefrom.\n\n\n"
                    f"Deponent")

        return "Section content not available."

    def generate_section(self, section, context): return self._t(section, context)

    def generate_all_sections(self, context):
        start = time.time()
        order = ["title_block","complaint_body","prayer","list_of_witnesses","list_of_documents","affidavit","evidence_affidavit"]
        sections = {s: self._t(s, context) for s in order}
        sections["_generation_time"] = round(time.time()-start, 2)
        sections["_full_text"] = ("\n\n"+"="*70+"\n\n").join(sections[k] for k in order)
        logger.info(f"All 7 sections generated in {sections['_generation_time']}s")
        return sections
