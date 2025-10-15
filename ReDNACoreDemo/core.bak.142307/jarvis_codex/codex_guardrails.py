"""
Jarvis-Codex Guardrails — Phase 1B
Hard constraints for HC-generated UI proposals.

Ensures HC can only propose small, safe text/style edits within allowed scope.
"""

import re
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path


class CodexGuardrails:
    """
    Validates proposal requests against hard constraints.

    Phase 1B scope: text_replace and style token swaps only.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "allowed_paths": [
                "web/src/",
                "devx/frontend/src/"
            ],
            "max_file_size_kb": 50,
            "allowed_change_types": [
                "text_replace",
                "style_token_swap"
            ],
            "min_confidence": 0.85,
            "max_diff_lines": 12,
            "max_label_chars": 80,
            "language_rules": {
                "concise": True,
                "neutral": True,
                "non_marketing": True
            }
        }

    def validate_proposal(
        self,
        proposal: Dict[str, Any],
        project_root: Optional[Path] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a proposal against all guardrails.

        Args:
            proposal: Proposal dict with scope, file, intent, suggested_change, confidence, source
            project_root: Optional project root path for file validation

        Returns:
            (is_valid, error_message)
        """

        # 1. Validate required fields
        required_fields = ["scope", "file", "intent", "suggested_change", "confidence", "source"]
        for field in required_fields:
            if field not in proposal:
                return False, f"Missing required field: {field}"

        # 2. Validate scope
        if proposal["scope"] != "frontend":
            return False, f"Invalid scope: {proposal['scope']} (only 'frontend' allowed)"

        # 3. Validate file path
        file_path = proposal["file"]
        is_valid_path, path_error = self._validate_file_path(file_path, project_root)
        if not is_valid_path:
            return False, path_error

        # 4. Validate change type
        change = proposal["suggested_change"]
        if "type" not in change:
            return False, "Missing change type in suggested_change"

        if change["type"] not in self.config["allowed_change_types"]:
            return False, f"Change type '{change['type']}' not allowed (allowed: {self.config['allowed_change_types']})"

        # 5. Validate change content
        is_valid_change, change_error = self._validate_change_content(change)
        if not is_valid_change:
            return False, change_error

        # 6. Validate confidence
        confidence = proposal["confidence"]
        if not isinstance(confidence, (int, float)):
            return False, f"Invalid confidence type: {type(confidence).__name__}"

        if confidence < self.config["min_confidence"]:
            return False, f"Confidence {confidence} below minimum {self.config['min_confidence']}"

        # 7. Validate diff size (if before/after provided)
        if change["type"] == "text_replace":
            is_valid_diff, diff_error = self._validate_diff_size(change)
            if not is_valid_diff:
                return False, diff_error

        # 8. Validate language rules (for text_replace)
        if change["type"] == "text_replace":
            is_valid_lang, lang_error = self._validate_language_rules(change)
            if not is_valid_lang:
                return False, lang_error

        return True, None

    def _validate_file_path(
        self,
        file_path: str,
        project_root: Optional[Path] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate file path against allowed paths."""

        # Check against allowed paths
        allowed = False
        for allowed_path in self.config["allowed_paths"]:
            if file_path.startswith(allowed_path):
                allowed = True
                break

        if not allowed:
            return False, f"File path not in allowed scopes: {self.config['allowed_paths']}"

        # Check file size if project root provided
        if project_root:
            full_path = project_root / file_path
            if full_path.exists():
                size_kb = full_path.stat().st_size / 1024
                if size_kb > self.config["max_file_size_kb"]:
                    return False, f"File size {size_kb:.1f}KB exceeds max {self.config['max_file_size_kb']}KB"

        # Check file extension (UI files only)
        if not file_path.endswith(('.tsx', '.ts', '.jsx', '.js', '.css')):
            return False, f"File type not allowed (must be .tsx, .ts, .jsx, .js, or .css)"

        return True, None

    def _validate_change_content(self, change: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate change content based on type."""

        change_type = change["type"]

        if change_type == "text_replace":
            if "before" not in change or "after" not in change:
                return False, "text_replace requires 'before' and 'after' fields"

            before = change["before"]
            after = change["after"]

            if not isinstance(before, str) or not isinstance(after, str):
                return False, "text_replace 'before' and 'after' must be strings"

            if before == after:
                return False, "text_replace 'before' and 'after' must be different"

            if len(before) == 0:
                return False, "text_replace 'before' cannot be empty"

        elif change_type == "style_token_swap":
            if "before_token" not in change or "after_token" not in change:
                return False, "style_token_swap requires 'before_token' and 'after_token' fields"

            # Validate tokens are CSS utility classes (tailwind-like)
            before_token = change["before_token"]
            after_token = change["after_token"]

            if not self._is_valid_style_token(before_token):
                return False, f"Invalid before_token: {before_token}"

            if not self._is_valid_style_token(after_token):
                return False, f"Invalid after_token: {after_token}"

        return True, None

    def _is_valid_style_token(self, token: str) -> bool:
        """Check if token is a valid CSS utility class."""
        # Simple validation: alphanumeric, hyphens, underscores
        return bool(re.match(r'^[a-zA-Z0-9\-_]+$', token))

    def _validate_diff_size(self, change: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate that diff is not too large."""

        before = change.get("before", "")
        after = change.get("after", "")

        # Count lines in before and after
        before_lines = before.count('\n') + 1
        after_lines = after.count('\n') + 1

        max_lines = max(before_lines, after_lines)

        if max_lines > self.config["max_diff_lines"]:
            return False, f"Diff too large: {max_lines} lines (max {self.config['max_diff_lines']})"

        return True, None

    def _validate_language_rules(self, change: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate language rules for text replacement."""

        after = change.get("after", "")

        # Check label length
        if len(after) > self.config["max_label_chars"]:
            return False, f"Label too long: {len(after)} chars (max {self.config['max_label_chars']})"

        # Check for marketing language (simple heuristic)
        marketing_words = [
            "amazing", "incredible", "revolutionary", "best", "perfect",
            "guaranteed", "free", "limited", "exclusive", "premium",
            "ultimate", "extraordinary", "exceptional", "outstanding"
        ]

        after_lower = after.lower()
        for word in marketing_words:
            if word in after_lower:
                return False, f"Marketing language detected: '{word}' (must be neutral)"

        # Check for excessive punctuation
        if after.count('!') > 0:
            return False, "Exclamation marks not allowed (must be neutral)"

        # Check for all caps (except acronyms ≤3 chars)
        words = after.split()
        for word in words:
            if word.isupper() and len(word) > 3:
                return False, f"All-caps word detected: '{word}' (must be concise)"

        return True, None

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of current guardrails."""
        return {
            "allowed_paths": self.config["allowed_paths"],
            "max_file_size_kb": self.config["max_file_size_kb"],
            "allowed_change_types": self.config["allowed_change_types"],
            "min_confidence": self.config["min_confidence"],
            "max_diff_lines": self.config["max_diff_lines"],
            "max_label_chars": self.config["max_label_chars"],
            "language_rules": self.config["language_rules"]
        }


def create_guardrails(config: Optional[Dict[str, Any]] = None) -> CodexGuardrails:
    """Factory function to create CodexGuardrails instance."""
    return CodexGuardrails(config)
