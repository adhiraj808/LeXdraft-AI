#!/usr/bin/env python3
"""
Run validator on template path and print detailed statistics.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.nlp.generator import LegalDraftGenerator
from app.nlp.fact_sheet import build_from_text
from app.nlp.validator import validate_draft
import json


def create_test_factsheet(prompt: str):
    """Create a FactSheet from a test prompt."""
    return build_from_text(prompt)


def run_validator_on_templates():
    """Generate drafts using templates only and validate them."""
    generator = LegalDraftGenerator()
    
    # Test prompts covering different case types
    test_prompts = [
        # Criminal - cheque bounce
        "Ramesh Kumar issued a cheque of Rs 5,00,000 to Suresh Sharma dated 15 March 2026 which bounced due to insufficient funds. Legal notice sent on 20 March 2026. No payment received within 15 days. Need complaint under Section 138 NI Act.",
        
        # Civil - commercial contract
        "Tata Steel failed to deliver goods worth Rs 50 crore to Indira Car Manufacturers as per contract dated March 2026 in Jamshedpur, seeking damages and specific performance under Section 73 of the Indian Contract Act",
        
        # Family Law - divorce
        "Priya wants divorce from Rahul on grounds of cruelty and desertion. Married 10 years, one child aged 7. Seeking custody and alimony of Rs 25,000/month. Bengaluru family court. Married 10 May 2015. Desertion since 1 Jan 2024.",
        
        # Criminal - assault
        "Ramesh Kumar was assaulted by Suresh Sharma on 10 Jan 2026 in Delhi. FIR lodged at Connaught Place PS under Section 323, 325 IPC. Medical report shows grievous hurt. Seeking prosecution. Delhi court.",
        
        # Labour - wrongful termination
        "Employee Rahul terminated by ABC Corp on 15 Jan 2026 without notice or retrenchment compensation. Employed for 5 years. Salary Rs 75,000/month. Seeking reinstatement and back wages. Labour Court Delhi.",
    ]
    
    all_results = []
    
    for i, prompt in enumerate(test_prompts):
        print(f"\n{'='*80}")
        print(f"Test Case {i+1}: {prompt[:60]}...")
        print(f"{'='*80}")
        
        # Create FactSheet
        fact_sheet = create_test_factsheet(prompt)
        
        # Generate using template only (no LLM)
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
        
        # Generate template sections
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
        
        # Validate
        validation = validate_draft(draft_sections, fact_sheet, raw_prompt=prompt)
        
        # Count invented by type
        invented_by_type = {
            "names": 0, "dates": 0, "amounts": 0, 
            "addresses": 0, "clauses": 0
        }
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
        for section in template_funcs:
            section_text = draft_sections.get(section, "")
            section_validation = validate_draft({section: section_text}, fact_sheet, raw_prompt=prompt)
            count = len(section_validation.get("errors", []))
            if count > 0:
                invented_by_function[section] = count
        
        total_invented = sum(invented_by_type.values())
        
        print(f"\nTotal invented: {total_invented}")
        print(f"By type: {invented_by_type}")
        print(f"By template function: {invented_by_function}")
        
        if invented_details:
            print("\nFlagged items:")
            for j, (itype, detail) in enumerate(invented_details[:20]):
                # Determine if true positive or false positive
                # True positive: actually invented (not in FactSheet)
                # False positive: actually in FactSheet but validator missed it
                label = "TP"  # Assume true positive for now
                print(f"  {j+1}. [{itype}] {detail} -> {label}")
        
        all_results.append({
            "prompt": prompt[:80],
            "total_invented": total_invented,
            "by_type": invented_by_type,
            "by_function": invented_by_function,
            "flagged": invented_details[:20]
        })
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    total_all = sum(r["total_invented"] for r in all_results)
    print(f"Total invented across all test cases: {total_all}")
    
    # Domain table
    print("\nPer-domain invented count:")
    for r in all_results:
        domain = r["prompt"].split()[0]  # rough domain from first word
        print(f"  {domain}: {r['total_invented']}")
    
    return all_results


if __name__ == "__main__":
    run_validator_on_templates()