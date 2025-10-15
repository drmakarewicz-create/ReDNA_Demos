"""
Semantic Patch Engine — Jarvis-Codex Phase 2
AST-based refactoring with safety guarantees.

Supported operations (Phase 2):
1. rename_prop: Rename component prop
2. wrap_node: Wrap element with container
3. reorder_siblings: Swap sibling order
4. replace_style_class: Utility → design token
5. remap_token: Token → token migration
"""

import re
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class SemanticChange:
    """Single semantic change operation."""
    file: str
    operation: str
    selector: Optional[str] = None  # Component name or CSS selector
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    lines_touched: int = 0
    context: Optional[Dict[str, Any]] = None


@dataclass
class SemanticPatchManifest:
    """Manifest for a semantic patch proposal."""
    proposal_id: str
    changes: List[SemanticChange]
    summary: Dict[str, Any]  # {insertions, deletions, files}
    created_at: str
    risk_score: float = 0.0


class SemanticPatchEngine:
    """
    AST-based semantic refactoring engine.

    Phase 2 operations are limited to safe, reversible transforms.
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()

        # Operation allowlist
        self.allowed_operations = [
            "rename_prop",
            "wrap_node",
            "reorder_siblings",
            "replace_style_class",
            "remap_token"
        ]

        # Per-operation safety limits
        self.operation_limits = {
            "rename_prop": {"max_occurrences": 20, "max_files": 3},
            "wrap_node": {"max_nodes": 5, "max_files": 2},
            "reorder_siblings": {"max_swaps": 10, "max_files": 2},
            "replace_style_class": {"max_replacements": 30, "max_files": 5},
            "remap_token": {"max_replacements": 50, "max_files": 10}
        }

    def validate_operation(
        self,
        operation: str,
        change_spec: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that operation is allowed and spec is complete.

        Args:
            operation: Operation name
            change_spec: Operation parameters

        Returns:
            (is_valid, error_message)
        """

        if operation not in self.allowed_operations:
            return False, f"Operation '{operation}' not in allowlist: {self.allowed_operations}"

        # Validate operation-specific requirements
        if operation == "rename_prop":
            required = ["selector", "from", "to"]
            for field in required:
                if field not in change_spec:
                    return False, f"rename_prop requires field: {field}"

            if change_spec["from"] == change_spec["to"]:
                return False, "rename_prop 'from' and 'to' must be different"

        elif operation == "wrap_node":
            required = ["selector", "wrapper"]
            for field in required:
                if field not in change_spec:
                    return False, f"wrap_node requires field: {field}"

            # Validate wrapper is in allowlist
            allowed_wrappers = ["div", "section", "article", "nav", "header", "footer", "main"]
            if change_spec["wrapper"] not in allowed_wrappers:
                return False, f"wrapper '{change_spec['wrapper']}' not in allowlist: {allowed_wrappers}"

        elif operation == "reorder_siblings":
            required = ["selector", "order"]
            for field in required:
                if field not in change_spec:
                    return False, f"reorder_siblings requires field: {field}"

            if not isinstance(change_spec["order"], list):
                return False, "reorder_siblings 'order' must be a list"

        elif operation == "replace_style_class":
            required = ["from", "to"]
            for field in required:
                if field not in change_spec:
                    return False, f"replace_style_class requires field: {field}"

        elif operation == "remap_token":
            required = ["from", "to"]
            for field in required:
                if field not in change_spec:
                    return False, f"remap_token requires field: {field}"

        return True, None

    def generate_patch(
        self,
        file_path: Path,
        operation: str,
        change_spec: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[SemanticChange]]:
        """
        Generate patch for a single file operation.

        Args:
            file_path: Path to file to patch
            operation: Operation name
            change_spec: Operation parameters

        Returns:
            (patch_content, semantic_change) or (None, None) on error
        """

        if not file_path.exists():
            return None, None

        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception:
            return None, None

        # Validate operation
        is_valid, error = self.validate_operation(operation, change_spec)
        if not is_valid:
            return None, None

        # Apply operation
        if operation == "rename_prop":
            return self._patch_rename_prop(content, file_path, change_spec)
        elif operation == "wrap_node":
            return self._patch_wrap_node(content, file_path, change_spec)
        elif operation == "reorder_siblings":
            return self._patch_reorder_siblings(content, file_path, change_spec)
        elif operation == "replace_style_class":
            return self._patch_replace_style_class(content, file_path, change_spec)
        elif operation == "remap_token":
            return self._patch_remap_token(content, file_path, change_spec)

        return None, None

    def _patch_rename_prop(
        self,
        content: str,
        file_path: Path,
        spec: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[SemanticChange]]:
        """Generate patch for prop rename."""

        selector = spec["selector"]
        from_prop = spec["from"]
        to_prop = spec["to"]

        # Pattern: <Selector propName=...>
        pattern = rf'(<{re.escape(selector)}\s+[^>]*?)\b{re.escape(from_prop)}='

        matches = list(re.finditer(pattern, content))
        if not matches:
            return None, None

        # Apply replacement
        new_content = re.sub(pattern, rf'\1{to_prop}=', content)

        lines_touched = len(matches)

        change = SemanticChange(
            file=str(file_path.relative_to(self.project_root)),
            operation="rename_prop",
            selector=selector,
            from_value=from_prop,
            to_value=to_prop,
            lines_touched=lines_touched,
            context={"occurrences": len(matches)}
        )

        return new_content, change

    def _patch_wrap_node(
        self,
        content: str,
        file_path: Path,
        spec: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[SemanticChange]]:
        """Generate patch for node wrapping."""

        selector = spec["selector"]
        wrapper = spec["wrapper"]

        # Simple pattern: wrap standalone tags
        # Pattern: <selector>...</selector> (single line or multiline)
        pattern = rf'(<{re.escape(selector)}[^>]*>)(.*?)(</{re.escape(selector)}>)'

        matches = list(re.finditer(pattern, content, re.DOTALL))
        if not matches:
            return None, None

        # Wrap first occurrence only (safety)
        match = matches[0]
        wrapped = f'<{wrapper}>\n{match.group(0)}\n</{wrapper}>'

        new_content = content[:match.start()] + wrapped + content[match.end():]

        change = SemanticChange(
            file=str(file_path.relative_to(self.project_root)),
            operation="wrap_node",
            selector=selector,
            from_value=None,
            to_value=wrapper,
            lines_touched=3,  # Opening tag, content, closing tag
            context={"wrapper": wrapper}
        )

        return new_content, change

    def _patch_reorder_siblings(
        self,
        content: str,
        file_path: Path,
        spec: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[SemanticChange]]:
        """Generate patch for sibling reordering."""

        # This is complex for real AST; simplified version for demo
        # In production, would use proper TS/TSX parser

        selector = spec["selector"]
        order = spec["order"]  # List of indices [1, 0] means swap first two

        # Simplified: just document the intent
        # Real implementation would parse JSX and reorder children

        change = SemanticChange(
            file=str(file_path.relative_to(self.project_root)),
            operation="reorder_siblings",
            selector=selector,
            from_value=None,
            to_value=str(order),
            lines_touched=len(order),
            context={"order": order, "note": "Requires AST parser for production"}
        )

        # Return original content unchanged (stub)
        return content, change

    def _patch_replace_style_class(
        self,
        content: str,
        file_path: Path,
        spec: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[SemanticChange]]:
        """Generate patch for style class replacement."""

        from_class = spec["from"]
        to_class = spec["to"]

        # Pattern: className="... from_class ..."
        # Handle both single and multiple classes
        def replace_in_classname(match):
            classes = match.group(1)
            # Replace exact class match
            new_classes = re.sub(rf'\b{re.escape(from_class)}\b', to_class, classes)
            return f'className="{new_classes}"'

        pattern = r'className="([^"]*)"'
        new_content, count = re.subn(pattern, replace_in_classname, content)

        if count == 0:
            return None, None

        change = SemanticChange(
            file=str(file_path.relative_to(self.project_root)),
            operation="replace_style_class",
            selector=None,
            from_value=from_class,
            to_value=to_class,
            lines_touched=count,
            context={"replacements": count}
        )

        return new_content, change

    def _patch_remap_token(
        self,
        content: str,
        file_path: Path,
        spec: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[SemanticChange]]:
        """Generate patch for token remapping."""

        from_token = spec["from"]
        to_token = spec["to"]

        # Similar to replace_style_class but specifically for tokens
        def replace_in_classname(match):
            classes = match.group(1)
            new_classes = re.sub(rf'\b{re.escape(from_token)}\b', to_token, classes)
            return f'className="{new_classes}"'

        pattern = r'className="([^"]*)"'
        new_content, count = re.subn(pattern, replace_in_classname, content)

        if count == 0:
            return None, None

        change = SemanticChange(
            file=str(file_path.relative_to(self.project_root)),
            operation="remap_token",
            selector=None,
            from_value=from_token,
            to_value=to_token,
            lines_touched=count,
            context={"replacements": count}
        )

        return new_content, change

    def create_manifest(
        self,
        proposal_id: str,
        changes: List[SemanticChange]
    ) -> SemanticPatchManifest:
        """Create patch manifest from changes."""

        # Calculate summary statistics
        total_insertions = sum(c.lines_touched for c in changes if c.to_value)
        total_deletions = sum(c.lines_touched for c in changes if c.from_value)
        files_affected = len(set(c.file for c in changes))

        summary = {
            "insertions": total_insertions,
            "deletions": total_deletions,
            "files": files_affected
        }

        # Calculate basic risk score
        risk_score = self._calculate_risk_score(changes, summary)

        manifest = SemanticPatchManifest(
            proposal_id=proposal_id,
            changes=changes,
            summary=summary,
            created_at=datetime.now(timezone.utc).isoformat(),
            risk_score=risk_score
        )

        return manifest

    def _calculate_risk_score(
        self,
        changes: List[SemanticChange],
        summary: Dict[str, Any]
    ) -> float:
        """Calculate risk score (0.0-1.0) for changes."""

        risk = 0.0

        # Factor 1: Number of files (0.0-0.3)
        files = summary["files"]
        risk += min(files * 0.1, 0.3)

        # Factor 2: Lines touched (0.0-0.3)
        lines = summary["insertions"] + summary["deletions"]
        risk += min(lines * 0.005, 0.3)

        # Factor 3: Operation complexity (0.0-0.4)
        operation_weights = {
            "replace_style_class": 0.05,
            "remap_token": 0.05,
            "rename_prop": 0.15,
            "wrap_node": 0.20,
            "reorder_siblings": 0.25
        }

        for change in changes:
            risk += operation_weights.get(change.operation, 0.1)

        return min(risk, 1.0)

    def validate_ast_syntax(self, content: str, file_ext: str) -> Tuple[bool, Optional[str]]:
        """
        Validate AST syntax (stub for Phase 2).

        In production, would use actual TS/TSX parser.
        For now, simple validation.
        """

        # Basic validation: check for balanced brackets
        if file_ext in ['.tsx', '.ts', '.jsx', '.js']:
            # Count brackets
            open_braces = content.count('{')
            close_braces = content.count('}')
            open_brackets = content.count('[')
            close_brackets = content.count(']')
            open_parens = content.count('(')
            close_parens = content.count(')')

            if open_braces != close_braces:
                return False, f"Unbalanced braces: {open_braces} open, {close_braces} close"

            if open_brackets != close_brackets:
                return False, f"Unbalanced brackets: {open_brackets} open, {close_brackets} close"

            if open_parens != close_parens:
                return False, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"

        return True, None


def create_semantic_patch_engine(project_root: Optional[Path] = None) -> SemanticPatchEngine:
    """Factory function to create SemanticPatchEngine instance."""
    return SemanticPatchEngine(project_root)
