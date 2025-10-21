#!/usr/bin/env python3
"""
Audit codebase for RR/Curiosity normalization issues.

Searches for:
1. RR values outside 0-100 range (e.g., 800, 1000)
2. Curiosity computed by rules other than 100 - RR
3. Ambiguous RR labels without percentile context
4. API responses that may leak non-normalized RR
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Patterns to search for
PATTERNS = [
    # RR values that look like 0-1000 scale
    (r'rr[_\s]*[=:]\s*\(.*\)\s*\*\s*1000', 'RR computed as * 1000 (0-1000 scale)'),
    (r'rr[_\s]*score\s*[/]\s*1000', 'RR divided by 1000 (0-1000 scale)'),
    (r'rr[_\s]*score\s*[=:]\s*[0-9]{3,4}[^0-9]', 'RR literal value > 100 (likely 0-1000)'),

    # Curiosity not equal to 100 - RR
    (r'curiosity\s*=\s*(?!100\s*-\s*rr)', 'Curiosity computed by non-standard rule'),
    (r'1\.0\s*-\s*.*rr', 'Curiosity using 1.0 - RR (should be 100 - RR)'),

    # Ambiguous labeling
    (r'"readiness".*[^%]', 'Readiness label without % context'),
    (r'rr_score.*[0-9]{3}', 'rr_score with 3+ digits (likely 0-1000)'),
]

def audit_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Audit a single file for RR/Curiosity issues.

    Returns list of (line_number, issue_type, line_text)
    """
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            for pattern, issue_type in PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append((line_num, issue_type, line.strip()))

    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}", file=sys.stderr)

    return issues


def main():
    root = Path(__file__).parent.parent
    core_dir = root / "ReDNACoreDemo" / "core"

    print("="*80)
    print("RR/Curiosity Normalization Audit")
    print("="*80)
    print()

    total_files = 0
    total_issues = 0

    # Audit all Python files in core/
    for py_file in core_dir.rglob("*.py"):
        issues = audit_file(py_file)

        if issues:
            total_files += 1
            total_issues += len(issues)

            rel_path = py_file.relative_to(root)
            print(f"\n{rel_path}")
            print("-" * 80)

            for line_num, issue_type, line_text in issues:
                print(f"  Line {line_num}: {issue_type}")
                print(f"    {line_text[:100]}")

    print()
    print("="*80)
    print(f"Total: {total_issues} issues in {total_files} files")
    print("="*80)


if __name__ == "__main__":
    main()
