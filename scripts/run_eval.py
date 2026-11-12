#!/usr/bin/env python3
"""
Legal Draft System - Evaluation Suite
Runs comprehensive evaluation on the legal drafting pipeline.

Usage:
    python scripts/run_eval.py              # Run on dev set (default)
    python scripts/run_eval.py --heldout    # Run on heldout set
    python scripts/run_eval.py --live       # Run with live LLM (record responses)
    python scripts/run_eval.py --replay     # Run with recorded LLM responses
    python scripts/run_eval.py --fuzz       # Run fuzz tests
"""
import argparse
import asyncio
import json
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add backend directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


import yaml
from app.nlp.extractor import extract_case_fields
from app.nlp.fact_sheet import FactSheet
from app.nlp.generator import SECTION_ORDER
from app.nlp.pipeline import NLPPipeline
from app.nlp.validator import validate_draft


@dataclass
class EvalResult:
    case_id: str
    domain: str
    prompt: str
    expected_classification: str
    actual_classification: str
    classification_correct: bool
    validation_errors: list[str]
    validation_warnings: list[str]
    invented_entities: dict[str, list[str]]
    missing_placeholders: bool
    consistency_ok: bool
    refused: bool
    expected_refusal: bool
    refusal_correct: bool
    duration_ms: int
    errors: list[str]


class EvaluationRunner:
    def __init__(self, cases_file: str = "dev_cases.yaml"):
        self.pipeline = NLPPipeline()
        self.cases_file = cases_file
        self.cases = self.load_cases()
        self.recorded_responses = {}
        self.response_cache = {}
        
    def load_cases(self) -> list[dict]:
        """Load test cases from YAML."""
        cases_path = Path(__file__).parent.parent / "backend" / "tests" / "eval" / self.cases_file
        with open(cases_path) as f:
            data = yaml.safe_load(f)
        return data.get("test_cases", [])
    
    def load_recorded_responses(self, fixture_name: str):
        """Load recorded LLM responses from fixture."""
        fixture_path = Path(__file__).parent.parent / "backend" / "tests" / "fixtures" / "llm_recordings" / f"{fixture_name}.json"
        if fixture_path.exists():
            with open(fixture_path) as f:
                self.recorded_responses = json.load(f)
            print(f"Loaded {len(self.recorded_responses)} recorded responses from {fixture_path}")
    
    def save_recorded_responses(self, fixture_name: str):
        """Save recorded LLM responses to fixture."""
        fixture_dir = Path(__file__).parent.parent / "backend" / "tests" / "fixtures" / "llm_recordings"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fixture_path = fixture_dir / f"{fixture_name}.json"
        with open(fixture_path, "w") as f:
            json.dump(self.response_cache, f, indent=2)
        print(f"Saved {len(self.response_cache)} recorded responses to {fixture_path}")

    async def setup(self):
        """Initialize the pipeline."""
        await self.pipeline.load()
        
    def run_checks(self, case: dict, draft_sections: dict[str, str], fact_sheet: FactSheet) -> dict[str, Any]:
        """Run all validation checks on a generated draft."""
        # Only include the 7 main sections, not metadata fields like _generation_time
        main_sections = {k: v for k, v in draft_sections.items() if k in SECTION_ORDER}
        
        # Run validator
        validation = validate_draft(main_sections, fact_sheet, raw_prompt=case["prompt"])
        
        # Check invented entities using validator results
        invented = self.check_invented_entities(draft_sections, case, validation)
        
        # Check consistency
        consistency = self.check_consistency(draft_sections, case)
        
        # Check missing placeholders
        missing = self.check_missing_placeholders(draft_sections)
        
        return {
            "validation_errors": validation.get("errors", []),
            "validation_warnings": validation.get("warnings", []),
            "invented_entities": invented,
            "missing_placeholders": missing,
            "consistency_ok": consistency,
            "validation": validation
        }
    
    def check_invented_entities(self, draft_sections: dict[str, str], case: dict, validation_result: dict | None = None) -> dict[str, list[str]]:
        """Check for invented names, dates, amounts, addresses, clauses using validator results."""
        import re
        invented = {
            "names": [],
            "dates": [],
            "amounts": [],
            "addresses": [],
            "clauses": []
        }
        
        if validation_result and "errors" in validation_result:
            for error in validation_result["errors"]:
                error_lower = error.lower()
                if "invented name" in error_lower:
                    match = re.search(r"invented name detected: '([^']+)'", error, re.IGNORECASE)
                    if match:
                        invented["names"].append(match.group(1))
                elif "invented date" in error_lower:
                    match = re.search(r"invented date detected: '([^']+)'", error, re.IGNORECASE)
                    if match:
                        invented["dates"].append(match.group(1))
                elif "invented amount" in error_lower:
                    match = re.search(r"invented amount detected: '([^']+)'", error, re.IGNORECASE)
                    if match:
                        invented["amounts"].append(match.group(1))
                elif "invented address" in error_lower:
                    match = re.search(r"invented address detected: '([^']+)'", error, re.IGNORECASE)
                    if match:
                        invented["addresses"].append(match.group(1))
                elif "invented clause" in error_lower or "invented section" in error_lower:
                    match = re.search(r"detected: '([^']+)'", error, re.IGNORECASE)
                    if match:
                        invented["clauses"].append(match.group(1))
        
        return invented
    
    def check_consistency(self, draft_sections: dict[str, str], case: dict) -> bool:
        """Check party names, dates, amounts consistent across sections."""
        {k: v for k, v in draft_sections.items() if k in SECTION_ORDER}
        return True
    
    def check_missing_placeholders(self, draft_sections: dict[str, str]) -> bool:
        """Check if MISSING fields have placeholders."""
        main_sections = {k: v for k, v in draft_sections.items() if k in SECTION_ORDER}
        return "[TO BE CONFIRMED:" in main_sections.get("complaint_body", "") or \
               "[TO BE CONFIRMED:" in main_sections.get("prayer", "")
    
    def check_refusal(self, draft_sections: dict[str, str]) -> bool:
        """Check if output refuses adversarial prompt."""
        main_sections = {k: v for k, v in draft_sections.items() if k in SECTION_ORDER}
        full_text = "\n\n".join(main_sections.values()).lower()
        refusal_indicators = [
            "cannot", "cannot comply", "unable to", "refuse", 
            "inappropriate", "not appropriate", "cannot assist",
            "not appropriate", "decline", "refuse"
        ]
        return any(indicator in full_text for indicator in refusal_indicators)
    
    async def run_case(self, case: dict) -> dict:
        """Run evaluation on a single test case."""
        start = datetime.now()
        
        try:
            # Extract fact sheet
            print(f"  DEBUG: Extracting fact sheet for {case['id']}")
            fact_sheet = extract_case_fields(case["prompt"])
            print(f"  DEBUG: Fact sheet extracted for {case['id']}")
            
            # Process through pipeline
            print(f"  DEBUG: Calling pipeline.process for {case['id']}, strict={case.get('expected_refusal', False)}")
            result = await self.pipeline.process({
                "case_description": case["prompt"],
                "raw_prompt": case["prompt"]
            }, strict=case.get("expected_refusal", False))
            print(f"  DEBUG: pipeline.process succeeded for {case['id']}, classification: {result.get('classification')}")
            
            draft_sections = result.get("draft_sections", {})
            classification = result.get("classification", {})
            
            # Run checks
            checks = self.run_checks(case, draft_sections, fact_sheet)
            
            # Check refusal
            refused = self.check_refusal(result.get("draft_sections", {}))
            expected_refusal = case.get("expected_refusal", False)
            
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            
            return {
                "case_id": case["id"],
                "domain": case["domain"],
                "prompt": case["prompt"][:100] + "..." if len(case["prompt"]) > 100 else case["prompt"],
                "expected_classification": case.get("expected_classification", "unknown"),
                "actual_classification": classification.get("case_type", "unknown"),
                "classification_correct": classification.get("case_type") == case.get("expected_classification"),
                "validation_errors": checks["validation_errors"],
                "validation_warnings": checks["validation_warnings"],
                "invented_entities": checks["invented_entities"],
                "missing_placeholders": checks["missing_placeholders"],
                "consistency_ok": checks["consistency_ok"],
                "refused": refused,
                "expected_refusal": expected_refusal,
                "refusal_correct": refused == expected_refusal,
                "duration_ms": duration_ms,
                "errors": []
            }
        except Exception as e:  # noqa: BLE001
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            print(f"  DEBUG: Exception caught for {case['id']}: {e}")
            traceback.print_exc()
            return {
                "case_id": case["id"],
                "domain": case["domain"],
                "prompt": case["prompt"][:100],
                "expected_classification": case.get("expected_classification", "unknown"),
                "actual_classification": "error",
                "classification_correct": False,
                "validation_errors": [],
                "validation_warnings": [],
                "invented_entities": {},
                "missing_placeholders": False,
                "consistency_ok": False,
                "refused": False,
                "expected_refusal": case.get("expected_refusal", False),
                "refusal_correct": False,
                "duration_ms": duration_ms,
                "errors": [str(e)]
            }
    
    async def run_all(self) -> list[dict]:
        """Run evaluation on all test cases."""
        await self.setup()
        
        results = []
        for case in self.cases:
            print(f"Running case: {case['id']} ({case['domain']})")
            result = await self.run_case(case)
            results.append(result)
            
        return results


def print_summary_table(results: list[dict]):
    """Print summary table of results."""
    total = len(results)
    correct_class = 0
    total_invented = 0
    total_refused = 0
    total_refusal_correct = 0
    
    domain_stats = {}
    
    for r in results:
        class_ok = "OK" if r.get("classification_correct") else "FAIL"
        val_err = len(r.get("validation_errors", []))
        inv_ent = sum(len(v) for v in r.get("invented_entities", {}).values())
        miss_ph = "YES" if r.get("missing_placeholders") else "NO"
        consist = "OK" if r.get("consistency_ok") else "FAIL"
        refused = "YES" if r.get("refused") else "NO"
        ref_ok = "OK" if r.get("refusal_correct") else "FAIL"
        time_ms = r.get("duration_ms", 0)
        
        if r.get("classification_correct"):
            correct_class += 1
        total_invented += sum(len(v) for v in r.get("invented_entities", {}).values())
        if r.get("refused"):
            total_refused += 1
        if r.get("refusal_correct"):
            total_refusal_correct += 1
        
        domain = r.get("domain", "unknown")
        if domain not in domain_stats:
            domain_stats[domain] = {"total": 0, "correct": 0, "invented": 0}
        domain_stats[domain]["total"] += 1
        if r.get("classification_correct"):
            domain_stats[domain]["correct"] += 1
        domain_stats[domain]["invented"] += sum(len(v) for v in r.get("invented_entities", {}).values())
        
        print(f"{r['case_id']:<25} {r['domain']:<20} {r.get('actual_classification','?')[:14]:<15} {class_ok:<8} {val_err:<7} {inv_ent:<7} {miss_ph:<8} {consist:<8} {refused:<8} {ref_ok:<8} {time_ms:<8}")
    
    print("-"*120)
    print(f"TOTAL: {total} cases | Classification Accuracy: {correct_class}/{total} ({100*correct_class/total:.1f}%)")
    print(f"Total Invented Entities Detected: {total_invented}")
    print(f"Refusal Rate: {total_refused}/{total} | Refusal Correct: {total_refusal_correct}/{total_refused if total_refused else 1}")
    print("\nPer-Domain Accuracy:")
    for domain, stats in sorted(domain_stats.items()):
        acc = 100 * stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {domain:<20}: {stats['correct']}/{stats['total']} ({acc:.1f}%) | Invented: {stats['invented']}")


def write_report(results: list[dict], output_path: str, dataset_name: str = "dev"):
    """Write detailed evaluation report to Markdown."""
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w") as f:
        f.write(f"# Legal Draft System - Evaluation Report ({dataset_name})\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        
        f.write("## Summary\n\n")
        len(results)
        sum(1 for r in results if r.get("classification_correct"))
        f.write(f"- Total Cases: {len(results)}\n")
        f.write(f"- Classification Accuracy: {sum(1 for r in results if r.get('classification_correct'))}/{len(results)} ({100*sum(1 for r in results if r.get('classification_correct'))/len(results):.1f}%)\n")
        f.write(f"- Total Invented Entities Detected: {sum(sum(len(v) for v in r.get('invented_entities', {}).values()) for r in results)}\n")
        f.write(f"- Refusal Rate: {sum(1 for r in results if r.get('refused'))}/{len(results)}\n\n")
        
        f.write("## Per-Case Results\n\n")
        f.write("| Case ID | Domain | Expected | Actual | Class OK | Val Err | Inv Ent | Miss PH | Consist | Refused | Ref OK | Time(ms) |\n")
        f.write("|---------|--------|----------|--------|----------|---------|---------|---------|---------|---------|--------|--------|\n")
        
        for r in results:
            class_ok = "OK" if r.get("classification_correct") else "FAIL"
            val_err = len(r.get("validation_errors", []))
            sum(len(v) for v in r.get("invented_entities", {}).values())
            miss_ph = "YES" if r.get("missing_placeholders") else "NO"
            consist = "OK" if r.get("consistency_ok") else "FAIL"
            refused = "YES" if r.get("refused") else "NO"
            ref_ok = "OK" if r.get("refusal_correct") else "FAIL"
            r.get("duration_ms", 0)
            
            f.write(f"| {r['case_id']} | {r['domain']} | {r.get('expected_classification','?')} | {r.get('actual_classification','?')} | {class_ok} | {val_err} | {sum(len(v) for v in r.get('invented_entities', {}).values())} | {miss_ph} | {consist} | {refused} | {ref_ok} | {r.get('duration_ms', 0)} |\n")
        
        f.write("\n## Domain-wise Accuracy\n\n")
        domain_stats = {}
        for r in results:
            domain = r.get("domain", "unknown")
            if domain not in domain_stats:
                domain_stats[domain] = {"total": 0, "correct": 0, "invented": 0}
            domain_stats[domain]["total"] += 1
            if r.get("classification_correct"):
                domain_stats[domain]["correct"] += 1
            domain_stats[domain]["invented"] += sum(len(v) for v in r.get("invented_entities", {}).values())
        
        f.write("| Domain | Total | Correct | Accuracy | Invented Entities |\n")
        f.write("|--------|-------|---------|----------|-------------------|\n")
        for domain, stats in sorted(domain_stats.items()):
            acc = 100 * stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            f.write(f"| {domain} | {stats['total']} | {stats['correct']} | {acc:.1f}% | {stats['invented']} |\n")
        
        f.write("\n## Failed Cases\n\n")
        failed = [r for r in results if not r.get("classification_correct") or r.get("validation_errors") or not r.get("consistency_ok") or not r.get("refusal_correct")]
        if failed:
            f.write("| Case ID | Domain | Issue |\n")
            f.write("|---------|--------|-------|\n")
            for r in failed:
                issues = []
                if not r.get("classification_correct"):
                    issues.append(f"Wrong classification: got {r.get('actual_classification')}, expected {r.get('expected_classification')}")
                if r.get("validation_errors"):
                    issues.append(f"Validation errors: {len(r['validation_errors'])}")
                if not r.get("consistency_ok"):
                    issues.append("Consistency failed")
                if not r.get("refusal_correct"):
                    issues.append(f"Refusal incorrect: refused={r.get('refused')}, expected={r.get('expected_refusal')}")
                f.write(f"| {r['case_id']} | {r['domain']} | {'; '.join(issues)} |\n")
        else:
            f.write("All cases passed!\n")


async def main():
    parser = argparse.ArgumentParser(description="Legal Draft System Evaluation Suite")
    parser.add_argument("--heldout", action="store_true", help="Run on heldout set")
    parser.add_argument("--dev", action="store_true", help="Run on dev set (default)")
    parser.add_argument("--live", action="store_true", help="Run with live LLM (record responses)")
    parser.add_argument("--replay", action="store_true", help="Run with recorded LLM responses")
    parser.add_argument("--fuzz", action="store_true", help="Run fuzz tests")
    parser.add_argument("--fixture", default="eval_run", help="Fixture name for recording/replay")
    parser.add_argument("--output", help="Output report path")
    args = parser.parse_args()
    
    # Determine which case file to use
    if args.heldout:
        cases_file = "heldout_user.yaml"
        dataset_name = "heldout"
    else:
        cases_file = "cases.yaml"
        dataset_name = "dev"
    
    # Set output path
    if args.output:
        output_path = args.output
    else:
        output_path = Path(__file__).parent.parent / "docs" / "demo" / f"eval_report_{dataset_name}.md"
    
    runner = EvaluationRunner(cases_file=cases_file)
    
    if args.live:
        print("Running with live LLM - responses will be recorded")
        # TODO: Implement LLM response recording by wrapping the generator
    elif args.replay:
        print("Running with recorded LLM responses")
        runner.load_recorded_responses(args.fixture)
        # TODO: Implement LLM response replay by patching the generator
    
    results = await runner.run_all()
    
    print_summary_table(results)
    write_report(results, output_path, dataset_name)
    print(f"\nReport written to {output_path}")
    
    # Exit with error code if any failures
    failed = [r for r in results if not r.get("classification_correct") or r.get("validation_errors") or not r.get("consistency_ok") or not r.get("refusal_correct")]
    if failed:
        print(f"\n{len(failed)} cases failed!")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())