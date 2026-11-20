#!/usr/bin/env python3
"""
Generate 40 random flagged items for human labeling.
Outputs to docs/demo/flagged_sample.csv
"""
import sys
import random
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.nlp.generator import LegalDraftGenerator
from app.nlp.fact_sheet import build_from_text
from app.nlp.validator import validate_draft

# Sample prompts from eval cases
TEST_PROMPTS = [
    "Ramesh Kumar issued a cheque of Rs 5,00,000 to Suresh Sharma dated 15 March 2026 which bounced due to insufficient funds. Legal notice sent on 20 March 2026. No payment received within 15 days. Need complaint under Section 138 NI Act.",
    "Tata Steel failed to deliver goods worth Rs 50 crore to Indira Car Manufacturers as per contract dated March 2026 in Jamshedpur, seeking damages and specific performance under Section 73 of the Indian Contract Act",
    "Priya wants divorce from Rahul on grounds of cruelty and desertion. Married 10 years, one child aged 7. Seeking custody and alimony of Rs 25,000/month. Bengaluru family court. Married 10 May 2015. Desertion since 1 Jan 2024.",
    "Ramesh Kumar was assaulted by Suresh Sharma on 10 Jan 2026 in Delhi. FIR lodged at Connaught Place PS under Section 323, 325 IPC. Medical report shows grievous hurt. Seeking prosecution. Delhi court.",
    "Employee Rahul terminated by ABC Corp on 15 Jan 2026 without notice or retrenchment compensation. Employed for 5 years. Salary Rs 75,000/month. Seeking reinstatement and back wages. Labour Court Delhi.",
    "State Bank of India lent Rs 50 lakh to Rajesh Kumar for home loan on 01/04/2022. EMI of Rs 45,000 not paid since January 2025. Outstanding Rs 12 lakh. Legal notice sent 10 March 2025. Seeking recovery under SARFAESI Act. Mumbai jurisdiction.",
    "Purchased defective washing machine from Samsung for Rs 45,000 on 01/01/2026. Defective within 15 days. Samsung refusing replacement. Seeking refund and compensation under Consumer Protection Act 2019. Bangalore.",
    "ABC Ltd and XYZ Pvt Ltd entered contract with PQR Traders for supply of materials worth Rs 1 crore. ABC and XYZ are joint suppliers. PQR failed to pay. Seeking joint recovery. Mumbai.",
]

def generate_flagged_items():
    generator = LegalDraftGenerator()
    all_items = []
    
    for prompt in TEST_PROMPTS:
        fact_sheet = build_from_text(prompt)
        
        ctx = {
            "case_type": fact_sheet.claim_type.value if fact_sheet.claim_type.value else "Civil",
            "petitioner": fact_sheet.parties[0].name if fact_sheet.parties else "Petitioner",
            "respondent": fact_sheet.parties[1].name if len(fact_sheet.parties) > 1 else "Respondent",
            "court": "HIGH COURT",
            "location": fact_sheet.place.value or "Delhi",
            "description": prompt,
            "statutes": fact_sheet.statutes_cited_by_user,
            "raw_prompt": prompt,
        }
        
        sections = generator._template_section("complaint_body", ctx)
        
        # Validate to get flagged items
        draft_sections = {k: "" for k in ["title_block", "complaint_body", "prayer", "list_of_witnesses", "list_of_documents", "affidavit", "evidence_affidavit"]}
        draft_sections["complaint_body"] = sections
        
        validation = validate_draft(draft_sections, fact_sheet, raw_prompt=prompt)
        
        for error in validation.get("errors", []):
            if "Invented name" in error or "Invented date" in error or "Invented amount" in error or "Invented address" in error or "Invented clause" in error:
                # Extract the phrase and context
                parts = error.split("'")
                phrase = parts[1] if len(parts) > 1 else error
                
                # Find the sentence containing the phrase
                sentence = ""
                for sent in sections.split("."):
                    if phrase in sent:
                        sentence = sent.strip() + "."
                        break
                if not sentence:
                    sentence = sections[:200]
                
                all_items.append({
                    "case_id": prompt[:50].replace('\n', ' '),
                    "type": error.split(":")[0].replace("Invented ", "").replace(" detected", ""),
                    "phrase": phrase,
                    "sentence": sentence,
                    "template_function": "complaint_body",
                    "label": ""  # Empty for human labeling
                })
        
        # Also check other template functions
        for func_name in ["title_block", "prayer", "list_of_witnesses", "list_of_documents", "affidavit", "evidence_affidavit"]:
            try:
                section_text = getattr(generator, f"_template_section")(func_name, ctx) if hasattr(generator, "_template_section") else generator._template_section(func_name, ctx)
                validation = validate_draft({func_name: section_text}, fact_sheet, raw_prompt=prompt)
                for error in validation.get("errors", []):
                    if "Invented" in error:
                        parts = error.split("'")
                        phrase = parts[1] if len(parts) > 1 else error
                        sentence = ""
                        for sent in section_text.split("."):
                            if phrase in sent:
                                sentence = sent.strip() + "."
                                break
                        if not sentence:
                            sentence = section_text[:200]
                        all_items.append({
                            "case_id": prompt[:50].replace('\n', ' '),
                            "type": error.split(":")[0].replace("Invented ", "").replace(" detected", ""),
                            "phrase": phrase,
                            "sentence": sentence,
                            "template_function": func_name,
                            "label": ""
                        })
            except:
                pass
    
    return all_items

def main():
    items = generate_flagged_items()
    
    # Select 40 random items (or all if fewer)
    random.seed(42)
    selected = random.sample(items, min(40, len(items)))
    
    output_path = Path(__file__).parent.parent / "docs" / "demo" / "flagged_sample.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "type", "phrase", "sentence", "template_function", "label"])
        writer.writeheader()
        writer.writerows(selected)
    
    print(f"Generated {len(selected)} flagged items to {output_path}")
    for item in selected:
        print(f"  [{item['type']}] {item['phrase'][:60]}... in {item['template_function']}")

if __name__ == "__main__":
    main()