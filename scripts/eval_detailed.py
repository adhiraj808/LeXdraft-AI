#!/usr/bin/env python3
"""
Detailed evaluation: invented counts by type, by template function, and 20 random flagged items with TP/FP labels.
"""
import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.nlp.generator import LegalDraftGenerator
from app.nlp.fact_sheet import build_from_text
from app.nlp.validator import validate_draft


def create_test_factsheet(prompt: str):
    return build_from_text(prompt)


def run_validation_on_generated(prompt: str, use_template_only: bool = False):
    """Generate draft and validate, returning detailed breakdown."""
    generator = LegalDraftGenerator()
    fact_sheet = create_test_factsheet(prompt)
    
    ctx = {
        "case_description": prompt,
        "raw_prompt": prompt,
        "case_type": fact_sheet.claim_type.value if fact_sheet.claim_type.value else "Civil",
        "fact_sheet": {
            "parties": [{"name": p.name, "role": p.role} for p in fact_sheet.parties],
            "contract_date": {"value": fact_sheet.contract_date.value},
            "delivery_date": {"value": fact_sheet.delivery_date.value},
            "incident_date": {"value": fact_sheet.incident_date.value},
            "contract_value": {"value": fact_sheet.contract_value.value},
            "damages_claimed": {"value": fact_sheet.damages_claimed.value},
            "place": {"value": fact_sheet.place.value},
            "claim_type": {"value": fact_sheet.claim_type.value},
            "claim_type_raw": {"value": fact_sheet.claim_type_raw.value},
            "statutes_cited_by_user": fact_sheet.statutes_cited_by_user,
            "relief_sought": [{"value": r.value} for r in fact_sheet.relief_sought],
            "has_arbitration_clause": {"value": fact_sheet.has_arbitration_clause.value},
        },
        "court": "HON'BLE COURT",
        "location": fact_sheet.place.value or "Delhi",
        "description": prompt,
    }
    
    if use_template_only:
        draft_sections = {}
        template_funcs = [
            "title_block", "complaint_body", "prayer", 
            "list_of_witnesses", "list_of_documents", 
            "affidavit", "evidence_affidavit"
        ]
        for section in template_funcs:
            try:
                draft_sections[section] = generator._template_section(section, ctx)
            except Exception as e:
                draft_sections[section] = f"ERROR: {e}"
    else:
        # Use the pipeline which tries LLM first
        import asyncio
        from app.nlp.pipeline import NLPPipeline
        pipeline = NLPPipeline()
        asyncio.run(pipeline.load())
        result = asyncio.run(pipeline.process({
            "case_description": prompt,
            "raw_prompt": prompt
        }, strict=False))
        draft_sections = {k: v for k, v in result.get("draft_sections", {}).items() if not k.startswith("_")}
    
    validation = validate_draft(draft_sections, fact_sheet, raw_prompt=prompt)
    
    # Count by type
    invented_by_type = {"names": 0, "dates": 0, "amounts": 0, "addresses": 0, "clauses": 0}
    invented_details = []
    
    for error in validation.get("errors", []):
        error_lower = error.lower()
        if "invented name" in error_lower:
            invented_by_type["names"] += 1
            invented_details.append(("name", error))
        elif "invented date" in error_lower:
            invented_by_type["dates"] += 1
            invented_details.append(("date", error))
        elif "invented amount" in error_lower:
            invented_by_type["amounts"] += 1
            invented_details.append(("amount", error))
        elif "invented address" in error_lower:
            invented_by_type["addresses"] += 1
            invented_details.append(("address", error))
        elif "invented clause" in error_lower or "invented section" in error_lower:
            invented_by_type["clauses"] += 1
            invented_details.append(("clause", error))
    
    # Count by template function
    invented_by_function = {}
    for section, text in draft_sections.items():
        if section.startswith("_"):
            continue
        section_validation = validate_draft({section: text}, fact_sheet, raw_prompt=prompt)
        count = len(section_validation.get("errors", []))
        if count > 0:
            invented_by_function[section] = count
    
    return {
        "total": sum(invented_by_type.values()),
        "by_type": invented_by_type,
        "by_function": invented_by_function,
        "details": invented_details,
        "draft_sections": draft_sections
    }


def label_item(itype: str, detail: str, fact_sheet, draft_sections, prompt: str) -> str:
    """Heuristic TP/FP label."""
    import re
    error = detail
    full_text = "\n\n".join(draft_sections.values())
    
    if "Invented name detected" in error:
        match = re.search(r"Invented name detected: '([^']+)'", error)
        if match:
            name = match.group(1)
            party_names = [p.name for p in fact_sheet.parties if p.name]
            template_artifacts = [
                "delhi through", "through counsel", "dated counsel", "delhi dated",
                "document annexure", "description document", "annexure", "annexure a",
                "sr description", "sr document", "exhibit cw", "exhibit pw", "exhibit ww",
                "verification", "deponent", "solemnly affirm", "authorised representative",
                "counsel", "advocate", "sr no", "description of document",
            ]
            name_lower = name.lower()
            if any(p.lower() == name_lower for p in party_names):
                return "FP"
            if any(art in name_lower for art in template_artifacts):
                return "FP"
            if name in prompt:
                return "FP"
            return "TP"
    
    if "Invented date detected" in error:
        match = re.search(r"Invented date detected: '([^']+)'", error)
        if match:
            date_str = match.group(1)
            fs_dates = []
            for field_name in ["contract_date", "delivery_date", "incident_date"]:
                field = getattr(fact_sheet, field_name, None)
                if field and field.value:
                    fs_dates.append(field.value.lower())
            for nd in fact_sheet.notice_dates:
                if nd.value:
                    fs_dates.append(nd.value.lower())
            if any(date_str.lower() in d for d in fs_dates):
                return "FP"
            template_dates = ["1 jan 2024", "jan 2024", "dec 2023", "december 2023", "january 2024"]
            if date_str.lower() in template_dates:
                return "FP"
            return "TP"
    
    if "Invented amount detected" in error:
        match = re.search(r"Invented amount detected: '([^']+)'", error)
        if match:
            amt_str = match.group(1)
            fs_amounts = []
            for field_name in ["contract_value", "damages_claimed"]:
                field = getattr(fact_sheet, field_name, None)
                if field and field.value:
                    fs_amounts.append(field.value.lower())
            if any(amt_str.lower() in a for a in fs_amounts):
                return "FP"
            return "TP"
    
    if "Invented address detected" in error:
        match = re.search(r"Invented address detected: '([^']+)'", error)
        if match:
            addr = match.group(1)
            if addr.lower() in ["flat in", "flat with"]:
                return "FP"
            return "TP"
    
    if "Invented clause" in error or "Invented section" in error:
        match = re.search(r"detected: '([^']+)'", error)
        if match:
            clause = match.group(1)
            statute_sections = set()
            for statute in fact_sheet.statutes_cited_by_user:
                sec_matches = re.findall(r"section\s+(\d+[a-z]?)", statute, re.IGNORECASE)
                for sec in sec_matches:
                    statute_sections.add(f"section {sec}")
            if any(stat in clause.lower() for stat in statute_sections):
                return "FP"
            if clause.lower() in ["schedule hereto", "schedule causing"]:
                return "FP"
            return "TP"
    
    return "?"


# Test prompts from eval
test_prompts = [
    "Ramesh Kumar issued a cheque of Rs 5,00,000 to Suresh Sharma dated 15 March 2026 which bounced due to insufficient funds. Legal notice sent on 20 March 2026. No payment received within 15 days. Need complaint under Section 138 NI Act.",
    "Tata Steel failed to deliver goods worth Rs 50 crore to Indira Car Manufacturers as per contract dated March 2026 in Jamshedpur, seeking damages and specific performance under Section 73 of the Indian Contract Act",
    "Priya wants divorce from Rahul on grounds of cruelty and desertion. Married 10 years, one child aged 7. Seeking custody and alimony of Rs 25,000/month. Bengaluru family court. Married 10 May 2015. Desertion since 1 Jan 2024.",
    "Ramesh Kumar was assaulted by Suresh Sharma on 10 Jan 2026 in Delhi. FIR lodged at Connaught Place PS under Section 323, 325 IPC. Medical report shows grievous hurt. Seeking prosecution. Delhi court.",
    "Employee Rahul terminated by ABC Corp on 15 Jan 2026 without notice or retrenchment compensation. Employed for 5 years. Salary Rs 75,000/month. Seeking reinstatement and back wages. Labour Court Delhi.",
]

print("=" * 80)
print("FULL EVAL (pipeline: LLM -> template fallback)")
print("=" * 80)

all_results = []
all_details = []

for prompt in test_prompts:
    result = run_validation_on_generated(prompt, use_template_only=False)
    fact_sheet = create_test_factsheet(prompt)
    
    # Label each detail
    labeled = []
    for itype, detail in result["details"]:
        label = label_item(itype, detail, fact_sheet, result["draft_sections"], prompt)
        labeled.append((itype, detail, label))
    
    all_details.extend(labeled)
    all_results.append(result)
    
    print(f"\nPrompt: {prompt[:60]}...")
    print(f"  Total: {result['total']}")
    print(f"  By type: {result['by_type']}")
    print(f"  By function: {result['by_function']}")

# Summary
total_all = sum(r["total"] for r in all_results)
print(f"\n{'='*80}")
print(f"TOTAL INVENTED (full eval): {total_all}")
print(f"{'='*80}")

# By type aggregate
agg_type = {"names": 0, "dates": 0, "amounts": 0, "addresses": 0, "clauses": 0}
agg_func = {}
for r in all_results:
    for k, v in r["by_type"].items():
        agg_type[k] += v
    for k, v in r["by_function"].items():
        agg_func[k] = agg_func.get(k, 0) + v

print(f"\nAggregate by type: {agg_type}")
print(f"Sum: {sum(agg_type.values())}")
print(f"\nAggregate by template function: {agg_func}")
print(f"Sum: {sum(agg_func.values())}")

# 20 random flagged items with TP/FP
print(f"\n{'='*80}")
print("20 RANDOM FLAGGED ITEMS WITH TP/FP LABELS")
print(f"{'='*80}")

random.shuffle(all_details)
for i, (itype, detail, label) in enumerate(all_details[:20]):
    # Replace non-ascii chars for safe printing
    safe_detail = detail.encode('ascii', 'replace').decode('ascii')
    print(f"  {i+1}. [{itype}] {safe_detail[:80]}... -> {label}")

print(f"\nTP count: {sum(1 for _, _, l in all_details if l == 'TP')}")
print(f"FP count: {sum(1 for _, _, l in all_details if l == 'FP')}")
print(f"? count: {sum(1 for _, _, l in all_details if l == '?')}")