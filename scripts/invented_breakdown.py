#!/usr/bin/env python3
"""Print invented entity breakdown by type and template function."""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.nlp.pipeline import NLPPipeline
from app.nlp.validator import validate_draft
from app.nlp.extractor import extract_case_fields
from app.nlp.generator import SECTION_ORDER
import yaml
from collections import defaultdict, Counter

async def main():
    pipeline = NLPPipeline()
    await pipeline.load()
    
    with open(Path(__file__).parent.parent / "backend" / "tests" / "eval" / "cases.yaml") as f:
        data = yaml.safe_load(f)
    cases = data.get("test_cases", [])
    
    # Track by type
    by_type = defaultdict(list)
    
    for case in cases:
        case_id = case["id"]
        prompt = case["prompt"]
        domain = case["domain"]
        
        result = await pipeline.process({
            "case_description": prompt,
            "raw_prompt": prompt
        }, strict=False)
        
        draft = result.get("draft_sections", {})
        fact_sheet = extract_case_fields(prompt)
        
        main = {k: v for k, v in draft.items() if k in SECTION_ORDER}
        validation = validate_draft(main, fact_sheet)
        
        for error in validation.get("errors", []):
            error_lower = error.lower()
            if "invented" not in error_lower:
                continue
            
            import re
            match = re.search(r"detected: '([^']+)'", error)
            if not match:
                continue
            entity = match.group(1)
            
            if "name" in error_lower:
                etype = "name"
            elif "date" in error_lower:
                etype = "date"
            elif "amount" in error_lower:
                etype = "amount"
            elif "address" in error_lower:
                etype = "address"
            elif "clause" in error_lower or "section" in error_lower:
                etype = "clause"
            else:
                etype = "other"
            
            by_type[etype].append((case_id, domain, entity))
    
    # Print first 40 invented entities
    print("First 40 invented entities:")
    print("-" * 80)
    count = 0
    for etype in ["name", "date", "amount", "address", "clause", "other"]:
        for case_id, domain, entity in by_type[etype]:
            if count >= 40:
                break
            print(f"{case_id:20s} {etype:8s} {entity[:50]}")
            count += 1
        if count >= 40:
            break
    
    # Print count grouped by type
    print("\n" + "=" * 80)
    print("Count by type:")
    total = 0
    for etype in ["name", "date", "amount", "address", "clause", "other"]:
        cnt = len(by_type[etype])
        total += cnt
        print(f"  {etype:8s}: {cnt}")
    print(f"  TOTAL: {total}")
    
    # Print count grouped by domain
    print("\nCount by domain:")
    domain_counts = Counter()
    for etype, items in by_type.items():
        for case_id, domain, entity in items:
            domain_counts[domain] += 1
    for domain, cnt in sorted(domain_counts.items(), key=lambda x: -x[1]):
        print(f"  {domain:25s}: {cnt}")

asyncio.run(main())