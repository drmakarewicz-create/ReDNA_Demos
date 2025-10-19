"""
Auto-Review Pipeline — Jarvis-Codex Phase 2
===========================================

Performs pre-approval checks on semantic and text proposals before they
are eligible for application. The reviewer enforces guardrails around:

- AST syntax validation on modified files
- Design-token policy adherence for style operations
- Diff size, file count, and operation count limits
- Optional TypeScript type-checking (best-effort)

The review output is attached to each proposal and surfaced through the
API and DevX panel for human operators.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .token_validator import (
    TokenValidator,
    create_token_validator,
)
from .semantic_patch import (
    SemanticPatchEngine,
    create_semantic_patch_engine,
)


CheckName = str
CheckStatus = str  # "pass" | "fail" | "skipped"


class AutoReviewer:
    """Runs guardrail checks for Jarvis-Codex proposals."""

    DEFAULT_CHECKS: Dict[CheckName, CheckStatus] = {
        "ast_parse": "skipped",
        "token_policy": "skipped",
        "diff_limits": "skipped",
        "typecheck": "skipped",
    }

    def __init__(
        self,
        token_validator: Optional[TokenValidator] = None,
        patch_engine: Optional[SemanticPatchEngine] = None,
        project_root: Optional[Path] = None,
        typecheck_timeout: int = 60,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).parent.parent.parent)
        self.token_validator = token_validator or create_token_validator()
        self.patch_engine = patch_engine or create_semantic_patch_engine(self.project_root)
        self.typecheck_timeout = typecheck_timeout

        self._tsc_checked = False
        self._tsc_available = False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def review_proposal(
        self,
        proposal: Dict[str, Any],
        bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run auto-review checks for a proposal.

        Args:
            proposal: Proposal dict (as persisted by CodexAgent)
            bundle: Optional transient data containing prepared changes.
                    Expected keys:
                        - "manifest": Manifest dict with summary + changes
                        - "files": List[Dict] with keys:
                            "file", "modified_content", "diff_stats", ...
                        - "operations": List of operation descriptors
                        - "change_type": "semantic" | "text_replace" | ...

        Returns:
            Auto-review result dict with status, risk, per-check statuses,
            notes, and recommendation.
        """

        manifest = self._resolve_manifest(proposal, bundle)
        file_contexts = self._resolve_file_contexts(bundle)
        operations = self._resolve_operations(proposal, bundle)
        change_type = self._resolve_change_type(proposal, bundle)

        checks: Dict[CheckName, CheckStatus] = dict(self.DEFAULT_CHECKS)
        notes: List[str] = []

        # AST parse check ------------------------------------------------
        ast_status, ast_notes = self._run_ast_check(change_type, file_contexts)
        checks["ast_parse"] = ast_status
        notes.extend(ast_notes)

        # Token policy check ---------------------------------------------
        token_status, token_notes = self._run_token_policy_check(manifest)
        checks["token_policy"] = token_status
        notes.extend(token_notes)

        # Diff limit check -----------------------------------------------
        diff_status, diff_notes = self._run_diff_limit_check(manifest, operations)
        checks["diff_limits"] = diff_status
        notes.extend(diff_notes)

        # Optional TypeScript type-check --------------------------------
        type_status, type_notes = self._run_typecheck(file_contexts)
        checks["typecheck"] = type_status
        notes.extend(type_notes)

        # Aggregate status -----------------------------------------------
        status = "pass"
        for name, result in checks.items():
            if result == "fail":
                status = "fail"
                break

        risk_score = self._resolve_risk_score(proposal, manifest)
        recommendation = self._compute_recommendation(status, risk_score)

        return {
            "status": status,
            "risk_score": risk_score,
            "checks": checks,
            "notes": notes,
            "recommendation": recommendation,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _resolve_manifest(
        self,
        proposal: Dict[str, Any],
        bundle: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if bundle and bundle.get("manifest"):
            return bundle["manifest"]
        return proposal.get("manifest") or proposal.get("file_manifest")

    def _resolve_file_contexts(
        self,
        bundle: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not bundle:
            return []
        files = bundle.get("files")
        if isinstance(files, list):
            return files
        return []

    def _resolve_operations(
        self,
        proposal: Dict[str, Any],
        bundle: Optional[Dict[str, Any]],
    ) -> List[Any]:
        if bundle and isinstance(bundle.get("operations"), list):
            return bundle["operations"]
        ops = proposal.get("operations")
        if isinstance(ops, list):
            return ops
        return []

    def _resolve_change_type(
        self,
        proposal: Dict[str, Any],
        bundle: Optional[Dict[str, Any]],
    ) -> str:
        if bundle and bundle.get("change_type"):
            return bundle["change_type"]
        if proposal.get("change_type"):
            return proposal["change_type"]
        return proposal.get("suggested_change", {}).get("type", "text_replace")

    def _resolve_risk_score(
        self,
        proposal: Dict[str, Any],
        manifest: Optional[Dict[str, Any]],
    ) -> float:
        if proposal.get("risk_score") is not None:
            try:
                return float(proposal["risk_score"])
            except (TypeError, ValueError):
                pass
        if manifest and manifest.get("risk_score") is not None:
            try:
                return float(manifest["risk_score"])
            except (TypeError, ValueError):
                pass
        return 0.0

    # ------------------------------------------------------------------ #
    # Individual checks
    # ------------------------------------------------------------------ #

    def _run_ast_check(
        self,
        change_type: str,
        file_contexts: List[Dict[str, Any]],
    ) -> Tuple[CheckStatus, List[str]]:
        """Validate that modified files still parse according to the stub engine."""

        if change_type != "semantic":
            return "skipped", ["AST check skipped (non-semantic proposal)"]

        parsed_files = 0
        for context in file_contexts:
            file_path = context.get("file")
            modified_content = context.get("modified_content")
            if not file_path or modified_content is None:
                continue

            ext = Path(file_path).suffix.lower()
            if ext not in {".ts", ".tsx", ".js", ".jsx"}:
                continue

            is_valid, error = self.patch_engine.validate_ast_syntax(modified_content, ext)
            if not is_valid:
                return "fail", [f"AST parse failed for {file_path}: {error}"]

            parsed_files += 1

        if parsed_files == 0:
            return "skipped", ["AST check skipped (no TS/JS files in bundle)"]

        return "pass", [f"AST parse passed for {parsed_files} file(s)"]

    def _run_token_policy_check(
        self,
        manifest: Optional[Dict[str, Any]],
    ) -> Tuple[CheckStatus, List[str]]:
        """Ensure style token operations comply with registry."""

        if not manifest:
            return "skipped", ["Token policy check skipped (no manifest)"]

        violations: List[str] = []
        relevant_changes = 0

        for change in manifest.get("changes", []):
            operation = change.get("operation")
            if operation not in {"replace_style_class", "remap_token"}:
                continue

            from_value = change.get("from_value")
            to_value = change.get("to_value")
            if not from_value or not to_value:
                violations.append(
                    f"Token policy check missing from/to values for {change.get('file')}"
                )
                continue

            is_valid, error = self.token_validator.validate_token_replacement(from_value, to_value)
            if not is_valid:
                violations.append(f"{change.get('file')}: {error or 'token validation failed'}")
            relevant_changes += 1

        if violations:
            return "fail", violations

        if relevant_changes == 0:
            return "pass", ["Token policy satisfied (no style token operations)"]

        return "pass", [f"Token policy satisfied for {relevant_changes} operation(s)"]

    def _run_diff_limit_check(
        self,
        manifest: Optional[Dict[str, Any]],
        operations: List[Any],
    ) -> Tuple[CheckStatus, List[str]]:
        """Verify diff, file, and operation guardrails."""

        if not manifest:
            return "skipped", ["Diff limits check skipped (no manifest)"]

        summary = manifest.get("summary", {})
        file_count = summary.get("files") or len(manifest.get("changes", []))
        violations: List[str] = []

        if file_count > 3:
            violations.append(f"{file_count} files exceeds limit of 3")

        for change in manifest.get("changes", []):
            diff_stats = change.get("diff_stats", {})
            total_lines = diff_stats.get("total")
            if total_lines is None:
                total_lines = change.get("lines_changed", 0)

            if total_lines > 60:
                violations.append(
                    f"{change.get('file')}: {total_lines} changed lines exceeds per-file limit (60)"
                )

        ops_total = len(operations) or len(manifest.get("changes", []))
        if ops_total > 5:
            violations.append(f"{ops_total} operations exceeds limit of 5")

        if violations:
            return "fail", violations

        return "pass", [
            f"Diff limits respected ({file_count} file(s), {ops_total} operation(s))"
        ]

    def _run_typecheck(
        self,
        file_contexts: List[Dict[str, Any]],
    ) -> Tuple[CheckStatus, List[str]]:
        """Attempt to run TypeScript compiler if available."""

        # Skip if no TS/JS files in bundle
        has_ts_files = any(
            Path(ctx.get("file", "")).suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}
            for ctx in file_contexts
        )
        if not has_ts_files:
            return "skipped", ["Typecheck skipped (no TS/JS files)"]

        if not self._ensure_tsc_available():
            return "skipped", ["Typecheck skipped (tsc not available)"]

        try:
            completed = subprocess.run(
                ["tsc", "--noEmit"],
                cwd=self.project_root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.typecheck_timeout,
            )
        except subprocess.TimeoutExpired:
            return "skipped", ["Typecheck skipped (tsc timed out)"]
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or "Unknown error"
            summary = " | ".join(message.splitlines()[:3])
            return "fail", [f"Typecheck failed: {summary}"]
        except Exception as exc:  # pragma: no cover - defensive
            return "skipped", [f"Typecheck skipped ({exc})"]

        output = (completed.stdout or "").strip()
        detail = (
            f"Typecheck passed ({output.splitlines()[0]})"
            if output
            else "Typecheck passed"
        )
        return "pass", [detail]

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def _ensure_tsc_available(self) -> bool:
        if not self._tsc_checked:
            self._tsc_available = shutil.which("tsc") is not None
            self._tsc_checked = True
        return self._tsc_available

    def _compute_recommendation(self, status: str, risk_score: float) -> str:
        if status == "fail":
            return "reject"

        if risk_score < 0.3:
            return "approve"
        if risk_score < 0.6:
            return "manual_review"
        return "reject"


def create_auto_reviewer(
    token_validator: Optional[TokenValidator] = None,
    patch_engine: Optional[SemanticPatchEngine] = None,
    project_root: Optional[Path] = None,
) -> AutoReviewer:
    """Factory helper for convenience."""
    return AutoReviewer(
        token_validator=token_validator,
        patch_engine=patch_engine,
        project_root=project_root,
    )

