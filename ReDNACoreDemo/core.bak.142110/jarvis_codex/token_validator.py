"""
Design-Token Validator — Jarvis-Codex Phase 2
Ensures all style changes use design tokens from registry.

Blocks arbitrary hex, rgb, or unregistered utility classes.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List


class TokenValidator:
    """
    Validates style changes against design-token registry.

    Phase 2 policy: All style changes must resolve to tokens.
    """

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or Path(__file__).parent / "design_tokens.json"
        self.registry = self._load_registry()

        # Build reverse lookup: token → utility
        self.token_to_utility = {}
        for category, mappings in self.registry.items():
            for utility, token in mappings.items():
                self.token_to_utility[token] = utility

    def _load_registry(self) -> Dict[str, Dict[str, str]]:
        """Load design-token registry from JSON."""
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Token registry not found: {self.registry_path}")

        with open(self.registry_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def validate_token_replacement(
        self,
        before: str,
        after: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a style token replacement.

        Args:
            before: Original utility class (e.g., "text-gray-600")
            after: Replacement token (e.g., "text-foreground-muted")

        Returns:
            (is_valid, error_message)
        """

        # Check if 'before' is in registry
        before_found = False
        before_category = None

        for category, mappings in self.registry.items():
            if before in mappings:
                before_found = True
                before_category = category
                expected_token = mappings[before]
                break

        if not before_found:
            return False, f"Utility class '{before}' not in registry"

        # Check if 'after' matches expected token
        if after != expected_token:
            return False, f"Invalid replacement: expected '{expected_token}' for '{before}', got '{after}'"

        return True, None

    def validate_style_class(self, class_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a single style class.

        Args:
            class_name: Class name to validate

        Returns:
            (is_valid, error_message)
        """

        # Check if it's a design token
        if class_name in self.token_to_utility:
            return True, None

        # Check if it's a registered utility (allowed as fallback)
        for category, mappings in self.registry.items():
            if class_name in mappings:
                return True, None

        # Check for forbidden patterns
        if self._is_arbitrary_style(class_name):
            return False, f"Arbitrary style not allowed: '{class_name}'"

        # If not in registry and not arbitrary, it might be a structural class (allowed)
        # Only block if it looks like a color/spacing/typography class
        if self._looks_like_styleable_class(class_name):
            return False, f"Unregistered style class: '{class_name}'"

        # Structural classes (flex, grid, etc.) are allowed
        return True, None

    def _is_arbitrary_style(self, class_name: str) -> bool:
        """Check if class uses arbitrary values (hex, rgb, etc.)."""

        # Tailwind arbitrary value syntax: [#hex], [rgb(...)]
        if '[' in class_name and ']' in class_name:
            return True

        # Direct hex colors
        if re.match(r'^#[0-9a-fA-F]{3,6}$', class_name):
            return True

        # RGB/RGBA patterns
        if re.match(r'rgba?\(', class_name):
            return True

        return False

    def _looks_like_styleable_class(self, class_name: str) -> bool:
        """Check if class looks like a color/spacing/typography class."""

        # Patterns that should be in registry
        style_prefixes = [
            'text-', 'bg-', 'border-',  # Colors
            'p-', 'px-', 'py-', 'pt-', 'pb-', 'pl-', 'pr-',  # Padding
            'm-', 'mx-', 'my-', 'mt-', 'mb-', 'ml-', 'mr-',  # Margin
            'gap-', 'space-',  # Gap/spacing
            'font-',  # Typography
        ]

        for prefix in style_prefixes:
            if class_name.startswith(prefix):
                return True

        return False

    def validate_className_change(
        self,
        before_classes: str,
        after_classes: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a className attribute change.

        Args:
            before_classes: Original className value
            after_classes: New className value

        Returns:
            (is_valid, error_message)
        """

        # Parse class lists
        before_list = before_classes.split()
        after_list = after_classes.split()

        # Find added and removed classes
        added = set(after_list) - set(before_list)
        removed = set(before_list) - set(after_list)

        # Validate all added classes
        for class_name in added:
            is_valid, error = self.validate_style_class(class_name)
            if not is_valid:
                return False, f"Added class validation failed: {error}"

        # Check if removals are replacing with tokens
        for class_name in removed:
            # If a utility is removed, there should be a token added
            expected_token = None
            for category, mappings in self.registry.items():
                if class_name in mappings:
                    expected_token = mappings[class_name]
                    break

            if expected_token and expected_token not in added:
                # Utility removed but token not added - might be intentional
                # This is a warning, not a blocker
                pass

        return True, None

    def get_token_for_utility(self, utility: str) -> Optional[str]:
        """Get design token for a utility class."""
        for category, mappings in self.registry.items():
            if utility in mappings:
                return mappings[utility]
        return None

    def get_utility_for_token(self, token: str) -> Optional[str]:
        """Get utility class for a design token."""
        return self.token_to_utility.get(token)

    def list_tokens_by_category(self, category: str) -> Dict[str, str]:
        """List all tokens in a category."""
        return self.registry.get(category, {})

    def get_all_categories(self) -> List[str]:
        """Get list of all token categories."""
        return list(self.registry.keys())


def create_token_validator(registry_path: Optional[Path] = None) -> TokenValidator:
    """Factory function to create TokenValidator instance."""
    return TokenValidator(registry_path)
