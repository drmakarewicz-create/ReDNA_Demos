"""
Codex Agent — Jarvis-Codex Phase 2
==================================

Manages the lifecycle of guarded UI edit proposals including:
- Proposal validation (scope, size, confidence)
- Diff + manifest generation for single and multi-file bundles
- Auto-review pipeline integration with risk scoring
- Atomic apply with per-file backups and rollback recovery
- Audit logging for traceability
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from .auto_review import AutoReviewer, create_auto_reviewer
from .semantic_patch import (
    SemanticChange,
    SemanticPatchEngine,
    create_semantic_patch_engine,
)
from .token_validator import TokenValidator, create_token_validator

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DEFAULT_CONFIG: Dict[str, Any] = {
    "allowed_scopes": [
        "web/src/",
        "devx/frontend/src/",
    ],
    "max_file_size_kb": 50,
    "min_confidence": 0.85,
    "backup_dir": "web/backups/",
    "proposals_log": "prompts/insights/jarvis_codex_proposals.jsonl",
    "audit_log": "prompts/insights/jarvis_codex_audit.jsonl",
    "bundle_dir": "data/codex_patches/",
}


# --------------------------------------------------------------------------- #
# Data Models
# --------------------------------------------------------------------------- #

@dataclass
class FileChangeRecord:
    """Per-file change metadata used for manifests and application."""

    file: str
    operation: str
    after_path: str
    checksum_before: str
    lines_changed: int
    diff_stats: Dict[str, int]
    diff: str
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    semantic_changes: List[SemanticChange] = field(default_factory=list)
    modified_content: Optional[str] = None

    def to_manifest_entry(self) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "file": self.file,
            "operation": self.operation,
            "lines_changed": self.lines_changed,
            "diff": self.diff,
            "diff_stats": self.diff_stats,
            "after_path": self.after_path,
            "checksum_before": self.checksum_before,
            "context": self.context,
        }

        if self.from_value is not None:
            entry["from_value"] = self.from_value
        if self.to_value is not None:
            entry["to_value"] = self.to_value

        return entry


@dataclass
class EditProposal:
    """Structured proposal persisted to the insights log."""

    proposal_id: str
    scope: str
    file: str
    intent: str
    suggested_change: Dict[str, Any]
    confidence: float
    source: str
    status: str  # "pending" | "applied" | "rejected" | "rolled_back"
    created_at: str
    checksum_before: Optional[str] = None
    patch_file: Optional[str] = None  # Backwards compatibility placeholder
    files: List[str] = field(default_factory=list)
    change_type: str = "text_replace"
    operations: List[Dict[str, Any]] = field(default_factory=list)
    manifest: Optional[Dict[str, Any]] = None
    file_manifest: Optional[List[Dict[str, Any]]] = None
    manifest_path: Optional[str] = None
    risk_score: float = 0.0
    auto_review: Optional[Dict[str, Any]] = None
    bundle_dir: Optional[str] = None
    applied_at: Optional[str] = None
    rolled_back_at: Optional[str] = None
    backup_bundle: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditProposal":
        allowed = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(**filtered)


# --------------------------------------------------------------------------- #
# Codex Agent
# --------------------------------------------------------------------------- #

class CodexAgent:
    """
    Guarded UI edit agent for Jarvis-Codex interface (Phase 2).

    Responsibilities:
    1. Validate incoming proposal data
    2. Generate diffs and manifests (single or multi-file)
    3. Run auto-review guardrails
    4. Persist proposals, manifests, and bundle artifacts
    5. Apply/rollback proposals atomically with backups
    6. Maintain audit trail
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        project_root: Optional[Path] = None,
        token_validator: Optional[TokenValidator] = None,
        patch_engine: Optional[SemanticPatchEngine] = None,
        auto_reviewer: Optional[AutoReviewer] = None,
    ) -> None:
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        self.project_root = Path(project_root)

        self.token_validator = token_validator or create_token_validator()
        self.semantic_engine = patch_engine or create_semantic_patch_engine(self.project_root)
        self.auto_reviewer = auto_reviewer or create_auto_reviewer(
            token_validator=self.token_validator,
            patch_engine=self.semantic_engine,
            project_root=self.project_root,
        )

        self._ensure_dirs()

    # ------------------------------------------------------------------ #
    # Directory helpers
    # ------------------------------------------------------------------ #

    def _ensure_dirs(self) -> None:
        """Ensure configured directories exist."""
        (self.project_root / self.config["backup_dir"]).mkdir(parents=True, exist_ok=True)
        proposals_log = self.project_root / self.config["proposals_log"]
        proposals_log.parent.mkdir(parents=True, exist_ok=True)
        audit_log = self.project_root / self.config["audit_log"]
        audit_log.parent.mkdir(parents=True, exist_ok=True)
        self._bundle_root().mkdir(parents=True, exist_ok=True)

    def _bundle_root(self) -> Path:
        return self.project_root / self.config["bundle_dir"]

    def _bundle_dir_for(self, proposal_id: str) -> Path:
        path = self._bundle_root() / proposal_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _backup_root(self, proposal_id: Optional[str] = None) -> Path:
        root = self.project_root / self.config["backup_dir"]
        if proposal_id:
            root = root / proposal_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def _is_allowed_scope(self, file_path: str) -> bool:
        normalized = file_path.replace("\\", "/")
        return any(normalized.startswith(scope) for scope in self.config["allowed_scopes"])

    def _validate_file_constraints(self, file_path: str) -> Tuple[bool, Optional[str]]:
        if not self._is_allowed_scope(file_path):
            return False, f"File path not in allowed scopes: {self.config['allowed_scopes']}"

        full_path = self.project_root / file_path
        if not full_path.exists():
            return False, f"File not found: {file_path}"

        size_kb = full_path.stat().st_size / 1024
        if size_kb > self.config["max_file_size_kb"]:
            return False, f"File size {size_kb:.1f}KB exceeds max {self.config['max_file_size_kb']}KB"

        return True, None

    def _validate_confidence(self, confidence: float) -> Tuple[bool, Optional[str]]:
        if confidence < self.config["min_confidence"]:
            return False, (
                f"Confidence {confidence} below minimum {self.config['min_confidence']}"
            )
        return True, None

    def validate_request(self, request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate Phase 1 style text replacement request (backwards compatible).
        """
        required = ["scope", "file", "intent", "suggested_change", "confidence", "source"]
        for field_name in required:
            if field_name not in request:
                return False, f"Missing required field: {field_name}"

        confidence = request["confidence"]
        ok, error = self._validate_confidence(confidence)
        if not ok:
            return False, error

        file_path = request["file"]
        ok, error = self._validate_file_constraints(file_path)
        if not ok:
            return False, error

        change = request["suggested_change"]
        if change.get("type") != "text_replace":
            return False, "generate_patch only supports 'text_replace' changes"

        if "before" not in change or "after" not in change:
            return False, "text_replace requires 'before' and 'after' fields"

        return True, None

    # ------------------------------------------------------------------ #
    # Checksum utilities
    # ------------------------------------------------------------------ #

    def compute_checksum(self, file_path: Path) -> str:
        """Compute SHA-256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ------------------------------------------------------------------ #
    # File/bundle helpers
    # ------------------------------------------------------------------ #

    def _bundle_filename(self, file_path: str, index: int, suffix: str) -> str:
        safe = file_path.replace("/", "__").replace("\\", "__")
        digest = hashlib.sha1(f"{file_path}-{index}".encode("utf-8")).hexdigest()[:8]
        return f"{index:02d}_{safe}_{digest}.{suffix}"

    def _write_after_file(
        self,
        bundle_dir: Path,
        file_path: str,
        index: int,
        content: str,
    ) -> str:
        filename = self._bundle_filename(file_path, index, "after")
        target = bundle_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target.relative_to(self.project_root))

    def _read_after_file(self, relative_path: str) -> str:
        target = self.project_root / relative_path
        if not target.exists():
            raise FileNotFoundError(f"Bundle artifact missing: {relative_path}")
        return target.read_text(encoding="utf-8")

    def _calculate_diff(
        self,
        original: str,
        modified: str,
        relative_path: str,
    ) -> Tuple[str, Dict[str, int]]:
        diff_lines = list(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm="",
            )
        )
        diff_text = "\n".join(diff_lines)

        added = sum(
            1
            for line in diff_lines
            if line.startswith("+") and not line.startswith("+++")
        )
        removed = sum(
            1
            for line in diff_lines
            if line.startswith("-") and not line.startswith("---")
        )

        return diff_text, {"added": added, "removed": removed, "total": added + removed}

    def _build_manifest(
        self,
        proposal_id: str,
        records: List[FileChangeRecord],
    ) -> Dict[str, Any]:
        summary = {
            "insertions": sum(rec.diff_stats.get("added", 0) for rec in records),
            "deletions": sum(rec.diff_stats.get("removed", 0) for rec in records),
            "files": len({rec.file for rec in records}),
        }

        semantic_changes: List[SemanticChange] = []
        for record in records:
            if record.semantic_changes:
                semantic_changes.extend(record.semantic_changes)
            else:
                semantic_changes.append(
                    SemanticChange(
                        file=record.file,
                        operation=record.operation,
                        selector=None,
                        from_value=record.from_value,
                        to_value=record.to_value,
                        lines_touched=record.lines_changed,
                        context=record.context,
                    )
                )

        try:
            risk_score = self.semantic_engine._calculate_risk_score(  # type: ignore[attr-defined]
                semantic_changes,
                summary,
            )
        except Exception:  # pragma: no cover - defensive
            risk_score = 0.0

        manifest = {
            "proposal_id": proposal_id,
            "changes": [record.to_manifest_entry() for record in records],
            "summary": summary,
            "risk_score": risk_score,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return manifest

    def _write_manifest(self, bundle_dir: Path, manifest: Dict[str, Any]) -> Path:
        manifest_path = bundle_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        return manifest_path

    def _load_manifest_for_proposal(self, proposal: EditProposal) -> Optional[Dict[str, Any]]:
        if proposal.manifest:
            return proposal.manifest

        if proposal.manifest_path:
            manifest_path = self.project_root / proposal.manifest_path
        else:
            manifest_path = self._bundle_dir_for(proposal.proposal_id) / "manifest.json"

        if not manifest_path.exists():
            return None

        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        return manifest

    def _build_bundle_context(
        self,
        records: List[FileChangeRecord],
        manifest: Dict[str, Any],
        change_type: str,
        operations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "files": [
                {
                    "file": record.file,
                    "modified_content": record.modified_content,
                    "diff_stats": record.diff_stats,
                    "operation": record.operation,
                    "context": record.context,
                }
                for record in records
            ],
            "manifest": manifest,
            "operations": operations,
            "change_type": change_type,
        }

    def _update_proposal_entry(self, proposal_id: str, updates: Dict[str, Any]) -> None:
        proposals_log = self.project_root / self.config["proposals_log"]
        if not proposals_log.exists():
            return

        entries: List[Dict[str, Any]] = []
        with open(proposals_log, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("proposal_id") == proposal_id:
                    entry.update(updates)
                entries.append(entry)

        with open(proposals_log, "w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------ #
    # Proposal generation (text + semantic)
    # ------------------------------------------------------------------ #

    def generate_patch(
        self,
        request: Dict[str, Any],
    ) -> Tuple[Optional[EditProposal], Optional[str]]:
        """
        Generate a single-file text replacement proposal (Phase 1 compatibility).
        """
        is_valid, error = self.validate_request(request)
        if not is_valid:
            return None, error

        file_path = request["file"]
        full_path = self.project_root / file_path

        try:
            original_content = full_path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - filesystem
            return None, f"Failed to read file: {exc}"

        change = request["suggested_change"]
        before = change["before"]
        after = change["after"]

        if before not in original_content:
            return None, f"Text not found in file: {before}"

        occurrences = original_content.count(before)
        if occurrences > 1:
            return None, f"Ambiguous: '{before}' appears {occurrences} times. Be more specific."

        modified_content = original_content.replace(before, after, 1)
        diff_text, diff_stats = self._calculate_diff(original_content, modified_content, file_path)

        proposal_id = str(uuid4())
        bundle_dir = self._bundle_dir_for(proposal_id)
        after_path = self._write_after_file(bundle_dir, file_path, 0, modified_content)

        checksum_before = self.compute_checksum(full_path)

        record = FileChangeRecord(
            file=file_path,
            operation="text_replace",
            after_path=after_path,
            checksum_before=checksum_before,
            lines_changed=diff_stats["total"],
            diff_stats=diff_stats,
            diff=diff_text,
            from_value=before,
            to_value=after,
            context={"occurrences": 1},
            semantic_changes=[
                SemanticChange(
                    file=file_path,
                    operation="text_replace",
                    selector=None,
                    from_value=before,
                    to_value=after,
                    lines_touched=diff_stats["total"],
                    context={"occurrences": 1},
                )
            ],
            modified_content=modified_content,
        )

        manifest = self._build_manifest(proposal_id, [record])
        manifest_path = self._write_manifest(bundle_dir, manifest)

        proposal = EditProposal(
            proposal_id=proposal_id,
            scope=request["scope"],
            file=file_path,
            intent=request["intent"],
            suggested_change=change,
            confidence=request["confidence"],
            source=request["source"],
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            checksum_before=checksum_before,
            files=[file_path],
            change_type="text_replace",
            operations=[{"file": file_path, "operation": "text_replace"}],
            manifest=manifest,
            file_manifest=manifest["changes"],
            manifest_path=str(manifest_path.relative_to(self.project_root)),
            risk_score=manifest["risk_score"],
            bundle_dir=str(bundle_dir.relative_to(self.project_root)),
        )

        bundle_context = self._build_bundle_context(
            [record],
            manifest,
            proposal.change_type,
            proposal.operations,
        )

        proposal.auto_review = self.auto_reviewer.review_proposal(
            proposal.to_dict(),
            bundle_context,
        )

        self._log_proposal(proposal)
        return proposal, None

    def propose_multi_file_change(
        self,
        files: List[str],
        operations: Optional[List[Dict[str, Any]]],
        intent: str,
        confidence: float,
        source: str,
        scope: str = "frontend",
        base_operation: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[EditProposal], Optional[str]]:
        """
        Create a semantic proposal spanning 1-3 files.
        """
        if not files:
            return False, None, "At least one file required"

        if len(files) > 3:
            return False, None, "Diff guardrail violated: max 3 files per proposal"

        ok, error = self._validate_confidence(confidence)
        if not ok:
            return False, None, error

        normalized_files: List[str] = []
        for file_path in files:
            ok, error = self._validate_file_constraints(file_path)
            if not ok:
                return False, None, error
            normalized_files.append(file_path)

        try:
            normalized_ops = self._normalize_operations(
                normalized_files,
                operations,
                base_operation,
            )
        except ValueError as exc:
            return False, None, str(exc)

        if len(normalized_ops) > 5:
            return False, None, "Diff guardrail violated: max 5 operations per proposal"

        proposal_id = str(uuid4())
        bundle_dir = self._bundle_dir_for(proposal_id)

        records: List[FileChangeRecord] = []
        ops_summary: List[Dict[str, Any]] = []

        for index, op_spec in enumerate(normalized_ops):
            file_path = op_spec["file"]
            operation = op_spec["operation"]
            params = op_spec.get("params", {})

            full_path = self.project_root / file_path
            try:
                original_content = full_path.read_text(encoding="utf-8")
            except Exception as exc:  # pragma: no cover - filesystem
                return False, None, f"Failed to read file {file_path}: {exc}"

            new_content, semantic_change = self.semantic_engine.generate_patch(
                full_path,
                operation,
                params,
            )

            if new_content is None or semantic_change is None:
                return False, None, f"Operation '{operation}' produced no change for {file_path}"

            diff_text, diff_stats = self._calculate_diff(original_content, new_content, file_path)
            checksum_before = self.compute_checksum(full_path)
            after_path = self._write_after_file(bundle_dir, file_path, index, new_content)

            record = FileChangeRecord(
                file=file_path,
                operation=operation,
                after_path=after_path,
                checksum_before=checksum_before,
                lines_changed=diff_stats["total"],
                diff_stats=diff_stats,
                diff=diff_text,
                from_value=semantic_change.from_value,
                to_value=semantic_change.to_value,
                context=semantic_change.context or {},
                semantic_changes=[semantic_change],
                modified_content=new_content,
            )
            records.append(record)
            ops_summary.append({"file": file_path, "operation": operation, "params": params})

        manifest = self._build_manifest(proposal_id, records)
        manifest_path = self._write_manifest(bundle_dir, manifest)

        primary_file = normalized_files[0]

        suggested_change = {
            "type": "semantic",
            "operations": ops_summary,
        }
        if base_operation:
            suggested_change.update(base_operation)

        proposal = EditProposal(
            proposal_id=proposal_id,
            scope=scope,
            file=primary_file,
            intent=intent,
            suggested_change=suggested_change,
            confidence=confidence,
            source=source,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            checksum_before=None,
            files=normalized_files,
            change_type="semantic",
            operations=ops_summary,
            manifest=manifest,
            file_manifest=manifest["changes"],
            manifest_path=str(manifest_path.relative_to(self.project_root)),
            risk_score=manifest["risk_score"],
            bundle_dir=str(bundle_dir.relative_to(self.project_root)),
        )

        bundle_context = self._build_bundle_context(
            records,
            manifest,
            proposal.change_type,
            ops_summary,
        )

        proposal.auto_review = self.auto_reviewer.review_proposal(
            proposal.to_dict(),
            bundle_context,
        )

        self._log_proposal(proposal)
        return True, proposal, None

    def _normalize_operations(
        self,
        files: List[str],
        operations: Optional[List[Dict[str, Any]]],
        base_operation: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Normalize operation specs into canonical structure."""
        normalized: List[Dict[str, Any]] = []

        if operations:
            for index, op in enumerate(operations):
                file_path = op.get("file") or (files[index] if index < len(files) else files[0])
                if not file_path:
                    raise ValueError("Operation missing 'file'")
                if file_path not in files:
                    raise ValueError(f"Operation references file outside bundle: {file_path}")

                operation = op.get("operation")
                if not operation:
                    raise ValueError("Operation missing 'operation' field")

                params = op.get("params")
                if params is None:
                    params = {k: v for k, v in op.items() if k not in {"file", "operation"}}

                normalized.append({"file": file_path, "operation": operation, "params": params})
        else:
            if not base_operation:
                raise ValueError("Semantic change requires operation specifications")

            operation = base_operation.get("operation")
            if not operation:
                raise ValueError("Semantic change missing 'operation'")

            params = {k: v for k, v in base_operation.items() if k not in {"type", "operation"}}

            for file_path in files:
                normalized.append({"file": file_path, "operation": operation, "params": params})

        seen_files: set[str] = set()
        for op in normalized:
            file_path = op["file"]
            if file_path in seen_files:
                raise ValueError("Multiple operations per file not supported in Phase 2")
            seen_files.add(file_path)

        return normalized

    # ------------------------------------------------------------------ #
    # Apply / rollback
    # ------------------------------------------------------------------ #

    def apply_patch(
        self,
        proposal_id: str,
        user: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        proposal = self._load_proposal(proposal_id)
        if not proposal:
            return False, f"Proposal not found: {proposal_id}"

        if proposal.status == "applied":
            return False, f"Proposal already applied: {proposal_id}"

        manifest = self._load_manifest_for_proposal(proposal)
        if not manifest:
            return False, "Proposal manifest missing; cannot apply"

        changes = manifest.get("changes", [])
        if not changes:
            return False, "Proposal contains no changes to apply"

        backup_root = self._backup_root(proposal_id)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup_bundle_dir = backup_root / timestamp
        backup_bundle_dir.mkdir(parents=True, exist_ok=True)

        applied_files: List[Tuple[Path, Path]] = []
        bundle_entries: List[Dict[str, Any]] = []

        try:
            for change in changes:
                relative_path = change["file"]
                target_path = self.project_root / relative_path

                if not target_path.exists():
                    raise FileNotFoundError(f"Target file missing during apply: {relative_path}")

                expected_checksum = change.get("checksum_before")
                if expected_checksum:
                    current_checksum = self.compute_checksum(target_path)
                    if current_checksum != expected_checksum:
                        raise RuntimeError(
                            f"Checksum mismatch for {relative_path} (expected {expected_checksum}, got {current_checksum})"
                        )

                # Backup original file
                backup_path = backup_bundle_dir / relative_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_path, backup_path)

                # Apply new content
                after_path = change.get("after_path")
                if not after_path:
                    raise RuntimeError(f"Missing after_path for {relative_path}")

                new_content = self._read_after_file(after_path)
                target_path.write_text(new_content, encoding="utf-8")

                applied_files.append((target_path, backup_path))
                bundle_entries.append(
                    {
                        "file": relative_path,
                        "backup_path": str(backup_path.relative_to(self.project_root)),
                    }
                )
        except Exception as exc:
            # Restore backups on failure
            for target_path, backup_path in applied_files:
                try:
                    shutil.copy2(backup_path, target_path)
                except Exception:  # pragma: no cover - best effort
                    logger.error("Failed to restore backup for %s", target_path)
            shutil.rmtree(backup_bundle_dir, ignore_errors=True)
            return False, str(exc)

        backup_manifest = {
            "proposal_id": proposal_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "bundle_dir": str(backup_bundle_dir.relative_to(self.project_root)),
            "files": bundle_entries,
        }

        with open(backup_bundle_dir / "manifest.json", "w", encoding="utf-8") as handle:
            json.dump(backup_manifest, handle, indent=2)

        latest_pointer = self._backup_root(proposal_id) / "latest.json"
        with open(latest_pointer, "w", encoding="utf-8") as handle:
            json.dump(backup_manifest, handle, indent=2)

        applied_at = datetime.now(timezone.utc).isoformat()
        self._update_proposal_entry(
            proposal_id,
            {
                "status": "applied",
                "applied_at": applied_at,
                "backup_bundle": backup_manifest["bundle_dir"],
            },
        )

        audit_details = {
            "files": [entry["file"] for entry in bundle_entries],
            "operations": [
                op if isinstance(op, str) else op.get("operation")
                for op in (proposal.operations or [])
            ],
            "risk_score": proposal.risk_score,
            "auto_review_status": (proposal.auto_review or {}).get("status") if proposal.auto_review else None,
            "backup_bundle": backup_manifest["bundle_dir"],
        }
        self._log_audit(proposal_id, "applied", user, audit_details)

        return True, {
            "proposal_id": proposal_id,
            "files": [entry["file"] for entry in bundle_entries],
            "backup_bundle": backup_manifest["bundle_dir"],
            "status": "applied",
            "applied_at": applied_at,
        }

    def rollback_proposal(
        self,
        proposal_id: str,
        user: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        proposal = self._load_proposal(proposal_id)
        if not proposal:
            return False, f"Proposal not found: {proposal_id}"

        latest_pointer = self._backup_root(proposal_id) / "latest.json"
        if not latest_pointer.exists():
            return False, "No backup bundle available for rollback"

        with open(latest_pointer, "r", encoding="utf-8") as handle:
            bundle_manifest = json.load(handle)

        restored_files: List[str] = []
        backup_paths: List[str] = []

        for entry in bundle_manifest.get("files", []):
            relative_file = entry["file"]
            backup_path = self.project_root / entry["backup_path"]

            if not backup_path.exists():
                return False, f"Backup file missing: {entry['backup_path']}"

            target_path = self.project_root / relative_file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, target_path)

            restored_files.append(relative_file)
            backup_paths.append(entry["backup_path"])

        rolled_back_at = datetime.now(timezone.utc).isoformat()
        self._update_proposal_entry(
            proposal_id,
            {
                "status": "rolled_back",
                "rolled_back_at": rolled_back_at,
            },
        )

        self._log_audit(
            proposal_id,
            "rolled_back",
            user,
            {
                "files_restored": restored_files,
                "backup_bundle": bundle_manifest.get("bundle_dir"),
            },
        )

        return True, {
            "proposal_id": proposal_id,
            "files_restored": restored_files,
            "backup_paths": backup_paths,
            "status": "rolled_back",
            "rolled_back_at": rolled_back_at,
        }

    # ------------------------------------------------------------------ #
    # Proposal lifecycle helpers
    # ------------------------------------------------------------------ #

    def reject_patch(
        self,
        proposal_id: str,
        user: str,
        reason: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        proposal = self._load_proposal(proposal_id)
        if not proposal:
            return False, f"Proposal not found: {proposal_id}"

        if proposal.status != "pending":
            return False, f"Proposal already {proposal.status}"

        self._update_proposal_entry(
            proposal_id,
            {
                "status": "rejected",
                "rejected_at": datetime.now(timezone.utc).isoformat(),
                "rejection_reason": reason or "Not specified",
            },
        )

        self._log_audit(
            proposal_id,
            "rejected",
            user,
            {
                "reason": reason or "Not specified",
            },
        )

        return True, None

    # ------------------------------------------------------------------ #
    # Query APIs
    # ------------------------------------------------------------------ #

    def list_proposals(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        proposals_log = self.project_root / self.config["proposals_log"]
        if not proposals_log.exists():
            return []

        proposals: List[Dict[str, Any]] = []
        with open(proposals_log, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if status and entry.get("status") != status:
                    continue
                proposals.append(entry)

        proposals.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return proposals[:limit]

    def get_patch_diff(
        self,
        proposal_id: str,
        file_path: Optional[str] = None,
    ) -> Optional[str]:
        proposal = self._load_proposal(proposal_id)
        if not proposal:
            return None

        manifest = self._load_manifest_for_proposal(proposal)
        if not manifest:
            return None

        changes = manifest.get("changes", [])
        if file_path:
            for change in changes:
                if change.get("file") == file_path:
                    return change.get("diff")

        if changes:
            return changes[0].get("diff")

        return None

    # ------------------------------------------------------------------ #
    # Persistence & audit
    # ------------------------------------------------------------------ #

    def _log_proposal(self, proposal: EditProposal) -> None:
        proposals_log = self.project_root / self.config["proposals_log"]
        entry = proposal.to_dict()

        try:
            with open(proposals_log, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        except Exception as exc:  # pragma: no cover - filesystem
            logger.error("Failed to log proposal: %s", exc)

    def _log_audit(
        self,
        proposal_id: str,
        action: str,
        user: str,
        details: Dict[str, Any],
    ) -> None:
        audit_log = self.project_root / self.config["audit_log"]
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "proposal_id": proposal_id,
            "action": action,
            "user": user,
            **details,
        }

        try:
            with open(audit_log, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        except Exception as exc:  # pragma: no cover - filesystem
            logger.error("Failed to log audit entry: %s", exc)

    def _load_proposal(self, proposal_id: str) -> Optional[EditProposal]:
        proposals_log = self.project_root / self.config["proposals_log"]
        if not proposals_log.exists():
            return None

        with open(proposals_log, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("proposal_id") == proposal_id:
                    return EditProposal.from_dict(entry)
        return None


# --------------------------------------------------------------------------- #
# Factory helper
# --------------------------------------------------------------------------- #

def create_codex_agent(
    config: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
) -> CodexAgent:
    return CodexAgent(config=config, project_root=project_root)

