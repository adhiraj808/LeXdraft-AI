#!/usr/bin/env python3
"""
CI Lint: Check static template text for case-specific proper nouns and disallowed digits.

This script scans the generator.py file for hardcoded template strings and
verifies they don't contain case-specific proper nouns (party names, specific places)
or digits outside allowed legal patterns.
"""

import ast
import re
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.nlp.legal_vocabulary import check_text


def extract_template_strings(filepath: Path) -> list:
    """Extract all string literals from template functions in generator.py"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    tree = ast.parse(content)
    template_strings = []
    
    # Target functions that contain template text
    target_functions = {
        '_witnesses_for',
        '_documents_for',
        '_affidavit_body',
        '_evidence_body',
        '_narrative_paragraphs',
        '_prayer_text',
        '_template_section',
        '_court_header',
        '_parties_block',
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_functions:
            # Extract all string constants from this function
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    template_strings.append((node.name, child.lineno, child.value))
                elif isinstance(child, ast.JoinedStr):  # f-strings
                    # Get the template parts (non-expression parts)
                    for part in child.values:
                        if isinstance(part, ast.Constant) and isinstance(part.value, str):
                            template_strings.append((node.name, child.lineno, part.value))
    
    return template_strings


def main():
    generator_path = Path(__file__).parent.parent / "backend" / "app" / "nlp" / "generator.py"
    template_strings = extract_template_strings(generator_path)
    
    all_issues = []
    for func_name, lineno, text in template_strings:
        issues = check_text(text)
        for issue_lineno, word, issue_type in issues:
            all_issues.append({
                'function': func_name,
                'line': lineno + issue_lineno - 1,
                'word': word,
                'issue_type': issue_type,
                'context': text[:100]
            })
    
    if all_issues:
        print("LINT FAILED: Found disallowed content in template strings:")
        print("-" * 80)
        for issue in all_issues:
            print(f"  Function: {issue['function']}")
            print(f"  Line: {issue['line']}")
            print(f"  Issue: {issue['issue_type']} - '{issue['word']}'")
            print(f"  Context: {issue['context']}")
            print()
        print(f"Total issues: {len(all_issues)}")
        return 1
    else:
        print("LINT PASSED: All template strings use allowed vocabulary only.")
        return 0


if __name__ == "__main__":
    sys.exit(main())