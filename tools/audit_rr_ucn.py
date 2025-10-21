#!/usr/bin/env python3
"""
UCN↔RR Conflation Audit Script

Scans the ReDNACoreDemo/core codebase for potential conflation between:
- UCN (User Confidence Number, 0-1000 internal audit metric)
- RR (Refinement Rating, 0-100 user-facing percentile)
- Curiosity (0-100, always = 100 - RR)

Generates a detailed report: docs/Phase9_RR_UCN_Audit_Report.md
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class AuditFinding:
    """Single audit finding."""
    file_path: str
    line_number: int
    code_snippet: str
    classification: str
    severity: str  # "critical", "warning", "info"
    description: str
    fix_suggestion: str


@dataclass
class AuditReport:
    """Complete audit report."""
    findings: List[AuditFinding] = field(default_factory=list)
    files_scanned: int = 0
    total_lines: int = 0

    def add_finding(self, finding: AuditFinding):
        self.findings.append(finding)

    def summary(self) -> Dict[str, Any]:
        critical = sum(1 for f in self.findings if f.severity == "critical")
        warnings = sum(1 for f in self.findings if f.severity == "warning")
        info = sum(1 for f in self.findings if f.severity == "info")

        classifications = {}
        for f in self.findings:
            classifications[f.classification] = classifications.get(f.classification, 0) + 1

        return {
            "files_scanned": self.files_scanned,
            "total_lines": self.total_lines,
            "total_findings": len(self.findings),
            "critical": critical,
            "warnings": warnings,
            "info": info,
            "classifications": classifications,
        }


class UCNRRAuditor:
    """Audits code for UCN↔RR conflation."""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.report = AuditReport()

        # Patterns to detect (compiled regex)
        self.patterns = {
            # RR assigned from UCN fields
            "rr_from_ucn": re.compile(r"""
                (rr|rr_score|readiness)\s*[=:]\s*
                (ucn|user_confidence|u\s*\*|c\s*\*|n\s*\*)
            """, re.VERBOSE | re.IGNORECASE),

            # RR calculated as 0-1000 scale
            "rr_1000_scale": re.compile(r"""
                (rr|rr_score|readiness)\s*[=:]\s*
                [^/\n]*?
                (1000|ucn.*1000|score.*1000)
            """, re.VERBOSE | re.IGNORECASE),

            # Curiosity computed as 1000 - X instead of 100 - RR
            "curiosity_1000": re.compile(r"""
                curiosity\s*[=:]\s*
                (1000\s*-|1000\.0\s*-)
            """, re.VERBOSE | re.IGNORECASE),

            # Legacy "Readiness Rating" terminology
            "readiness_legacy": re.compile(r"""
                (Readiness\s+Rating|readiness_rating)
            """, re.VERBOSE | re.IGNORECASE),

            # Direct assignment rr = ucn (variable names)
            "rr_equals_ucn": re.compile(r"""
                \brr\s*=\s*ucn\b
            """, re.VERBOSE | re.IGNORECASE),

            # UCN exposed as RR in return/response
            "ucn_as_rr_return": re.compile(r"""
                ["']rr["']\s*:\s*(ucn|u\s*\*|node\.ucn)
            """, re.VERBOSE | re.IGNORECASE),

            # RR > 100 checks (likely legacy 0-1000)
            "rr_greater_100": re.compile(r"""
                \brr\s*(>|>=)\s*(100|200|500|1000)
            """, re.VERBOSE | re.IGNORECASE),

            # Divide by 10 operations (0-1000 → 0-100 conversion hints)
            "divide_by_10": re.compile(r"""
                (rr|rr_score)\s*/\s*10
            """, re.VERBOSE | re.IGNORECASE),
        }

        # Keywords to search in file content
        self.keywords = ["ucn", "rr", "curiosity", "readiness", "refinement"]

    def scan_file(self, file_path: Path):
        """Scan a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                self.report.total_lines += len(lines)

            # Check if file mentions relevant keywords
            content = ''.join(lines)
            if not any(kw in content.lower() for kw in self.keywords):
                return  # Skip irrelevant files

            # Line-by-line analysis
            for i, line in enumerate(lines, start=1):
                self._check_line(file_path, i, line, lines)

            # AST-based analysis for more complex patterns
            try:
                tree = ast.parse(content, filename=str(file_path))
                self._check_ast(file_path, tree, lines)
            except SyntaxError:
                pass  # Skip files with syntax errors

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

    def _check_line(self, file_path: Path, line_num: int, line: str, all_lines: List[str]):
        """Check a single line for patterns."""

        # Skip comments and docstrings
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            return

        # Check each pattern
        for pattern_name, pattern in self.patterns.items():
            if pattern.search(line):
                self._add_pattern_finding(file_path, line_num, line, pattern_name)

    def _add_pattern_finding(self, file_path: Path, line_num: int, line: str, pattern_name: str):
        """Add a finding based on pattern match."""

        classifications = {
            "rr_from_ucn": ("UCN→RR Conflation", "critical",
                            "RR is being assigned from UCN fields (u, c, n)",
                            "Use rr_to_percentile() adapter to convert UCN to RR percentile"),

            "rr_1000_scale": ("RR 0-1000 Scale", "critical",
                              "RR is computed on 0-1000 scale instead of 0-100 percentile",
                              "Ensure RR is computed as percentile (0-100), not raw UCN score"),

            "curiosity_1000": ("Curiosity Legacy Formula", "critical",
                               "Curiosity computed as 1000-X instead of 100-RR",
                               "Change to: curiosity = 100.0 - rr"),

            "readiness_legacy": ("Legacy Terminology", "warning",
                                 "Uses obsolete 'Readiness Rating' instead of 'Refinement Rating'",
                                 "Update terminology to 'Refinement Rating' (RR)"),

            "rr_equals_ucn": ("Direct UCN→RR Assignment", "critical",
                              "Direct assignment rr = ucn without percentile conversion",
                              "Use rr_to_percentile() adapter to compute percentile"),

            "ucn_as_rr_return": ("UCN Leaked as RR", "critical",
                                 "UCN value returned under 'rr' key in API response",
                                 "Ensure normalize_egress is applied before returning"),

            "rr_greater_100": ("RR > 100 Check", "warning",
                               "Code checks if RR > 100, suggesting 0-1000 scale legacy",
                               "This is likely adapter code (OK) or legacy data handling"),

            "divide_by_10": ("0-1000 → 0-100 Conversion", "info",
                             "Dividing by 10 suggests 0-1000 → 0-100 normalization",
                             "Verify this is intentional adapter logic"),
        }

        classification, severity, description, fix = classifications.get(
            pattern_name,
            ("Unknown Pattern", "info", "Matched pattern: " + pattern_name, "Review manually")
        )

        # Skip false positives from adapter/normalize files (they're intentionally handling both scales)
        if "normalize_egress.py" in str(file_path) or "rr_adapter.py" in str(file_path):
            if pattern_name in ["rr_greater_100", "divide_by_10"]:
                severity = "info"  # Expected in adapter code

        finding = AuditFinding(
            file_path=str(file_path.relative_to(self.root_dir.parent)),
            line_number=line_num,
            code_snippet=line.strip(),
            classification=classification,
            severity=severity,
            description=description,
            fix_suggestion=fix,
        )

        self.report.add_finding(finding)

    def _check_ast(self, file_path: Path, tree: ast.AST, lines: List[str]):
        """Check AST for more complex patterns (function calls, assignments)."""

        class ASTVisitor(ast.NodeVisitor):
            def __init__(self, auditor, file_path, lines):
                self.auditor = auditor
                self.file_path = file_path
                self.lines = lines

            def visit_Assign(self, node):
                """Check assignments like rr = ucn or curiosity = ..."""
                try:
                    # Check if assigning to 'rr' or 'curiosity'
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id in ['rr', 'rr_score', 'curiosity']:
                                # Check if value is UCN-related
                                if isinstance(node.value, ast.Name) and node.value.id == 'ucn':
                                    line_num = node.lineno
                                    line = self.lines[line_num - 1] if line_num <= len(self.lines) else ""
                                    self.auditor._add_pattern_finding(
                                        self.file_path, line_num, line, "rr_equals_ucn"
                                    )
                except Exception:
                    pass

                self.generic_visit(node)

        visitor = ASTVisitor(self, file_path, lines)
        visitor.visit(tree)

    def scan_directory(self, directory: Path = None):
        """Scan all Python files in directory."""
        if directory is None:
            directory = self.root_dir

        for py_file in directory.rglob("*.py"):
            # Skip __pycache__ and test files for now (can include later)
            if "__pycache__" in str(py_file):
                continue

            self.report.files_scanned += 1
            self.scan_file(py_file)

    def generate_markdown_report(self, output_path: str):
        """Generate markdown report."""

        summary = self.report.summary()

        # Group findings by severity
        critical = [f for f in self.report.findings if f.severity == "critical"]
        warnings = [f for f in self.report.findings if f.severity == "warning"]
        info = [f for f in self.report.findings if f.severity == "info"]

        with open(output_path, 'w') as f:
            f.write("# Phase 9: UCN↔RR Conflation Audit Report\n\n")
            f.write("**Generated:** " + __import__('datetime').datetime.now().isoformat() + "\n\n")

            # Executive Summary
            f.write("## Executive Summary\n\n")
            f.write(f"- **Files Scanned:** {summary['files_scanned']}\n")
            f.write(f"- **Total Lines:** {summary['total_lines']:,}\n")
            f.write(f"- **Total Findings:** {summary['total_findings']}\n")
            f.write(f"  - Critical: {summary['critical']}\n")
            f.write(f"  - Warnings: {summary['warnings']}\n")
            f.write(f"  - Info: {summary['info']}\n\n")

            f.write("### Findings by Classification\n\n")
            for classification, count in sorted(summary['classifications'].items(),
                                                key=lambda x: x[1], reverse=True):
                f.write(f"- {classification}: {count}\n")
            f.write("\n")

            # Terminology Reference
            f.write("## Terminology Reference\n\n")
            f.write("| Term | Range | Purpose | Visibility |\n")
            f.write("|------|-------|---------|------------|\n")
            f.write("| **UCN** | 0-1000 | Internal confidence audit | Hidden |\n")
            f.write("| **RR** | 0-100 | User-facing percentile | Visible |\n")
            f.write("| **Curiosity** | 0-100 | Inverse of RR (= 100 - RR) | Hidden |\n\n")

            # Critical Findings
            if critical:
                f.write("## Critical Findings\n\n")
                f.write("These require immediate attention as they may leak UCN as RR or "
                        "use incorrect formulas.\n\n")
                self._write_findings_table(f, critical)

            # Warnings
            if warnings:
                f.write("## Warnings\n\n")
                f.write("These should be reviewed but may not cause functional issues.\n\n")
                self._write_findings_table(f, warnings)

            # Info
            if info:
                f.write("## Informational\n\n")
                f.write("These are likely intentional (e.g., adapter logic) but flagged for completeness.\n\n")
                self._write_findings_table(f, info)

            # Recommendations
            f.write("## Recommendations\n\n")
            f.write("1. **Apply egress normalization everywhere**: Ensure all API endpoints use "
                    "`normalize_egress.py` before returning RR/Curiosity.\n")
            f.write("2. **Never compute RR directly from UCN**: Always use `rr_to_percentile()` "
                    "adapter which handles reference population percentiles.\n")
            f.write("3. **Enforce curiosity formula**: Always `curiosity = 100.0 - rr`, never "
                    "`1000 - ucn`.\n")
            f.write("4. **Update terminology**: Replace all 'Readiness Rating' with 'Refinement Rating'.\n")
            f.write("5. **Add runtime guards**: Implement debug endpoint `/core/debug/rr_audit/{user_id}` "
                    "to detect mismatches in production.\n\n")

    def _write_findings_table(self, f, findings: List[AuditFinding]):
        """Write findings as markdown table."""
        for finding in findings:
            f.write(f"### {finding.classification}\n\n")
            f.write(f"**File:** `{finding.file_path}:{finding.line_number}`\n\n")
            f.write(f"**Code:**\n```python\n{finding.code_snippet}\n```\n\n")
            f.write(f"**Issue:** {finding.description}\n\n")
            f.write(f"**Fix:** {finding.fix_suggestion}\n\n")
            f.write("---\n\n")


def main():
    """Run audit."""
    parser = argparse.ArgumentParser(
        description="Audit ReDNA codebase for UCN/RR conflation issues"
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit with code 1 if critical issues found"
    )
    parser.add_argument(
        "--max-critical",
        type=int,
        default=None,
        help="Maximum allowed critical issues (exit code 1 if exceeded)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print summary, not full details"
    )

    args = parser.parse_args()

    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent / "ReDNACoreDemo" / "core"

    if not project_root.exists():
        print(f"Error: {project_root} does not exist")
        sys.exit(1)

    if not args.quiet:
        print(f"Scanning: {project_root}")

    auditor = UCNRRAuditor(root_dir=project_root)
    auditor.scan_directory()

    # Generate report
    report_path = script_dir.parent / "docs" / "Phase9_RR_UCN_Audit_Report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    auditor.generate_markdown_report(str(report_path))

    summary = auditor.report.summary()

    if not args.quiet:
        print(f"\n✅ Audit complete!")
        print(f"   Files scanned: {summary['files_scanned']}")
        print(f"   Total findings: {summary['total_findings']}")
        print(f"   Critical: {summary['critical']}")
        print(f"   Warnings: {summary['warnings']}")
        print(f"   Info: {summary['info']}")
        print(f"\n📄 Report: {report_path}")
    else:
        print(f"Critical: {summary['critical']}, Warnings: {summary['warnings']}, Info: {summary['info']}")

    # Check exit conditions
    critical_count = summary['critical']

    if args.fail_on_critical and critical_count > 0:
        print(f"\n❌ FAIL: {critical_count} critical issue(s) found")
        sys.exit(1)

    if args.max_critical is not None and critical_count > args.max_critical:
        print(f"\n❌ FAIL: {critical_count} critical issues exceed max allowed ({args.max_critical})")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
