"""
Jarvis-Codex Proposal Generator — Phase 1B
Enables Head Coach to propose small, safe UI copy/style edits.

Heuristics + optional LLM assist for text improvements.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    anthropic = None
    HAS_ANTHROPIC = False

from .codex_guardrails import create_guardrails


class ProposalGenerator:
    """
    Generates UI improvement proposals for Head Coach.

    Identifies candidate text/style edits and submits to Jarvis-Codex.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        guardrails_config: Optional[Dict[str, Any]] = None,
        llm_client: Optional[Any] = None  # anthropic.Anthropic if available
    ):
        self.project_root = project_root or Path.cwd()
        self.guardrails = create_guardrails(guardrails_config)
        self.llm_client = llm_client

        # Candidate patterns for text nodes (labels, headings, tooltips)
        self.text_patterns = [
            r'<h[1-6][^>]*>([^<]{1,120})</h[1-6]>',  # Headings
            r'<button[^>]*>([^<]{1,120})</button>',  # Buttons
            r'<label[^>]*>([^<]{1,120})</label>',  # Labels
            r'title="([^"]{1,120})"',  # Tooltips
            r'placeholder="([^"]{1,120})"',  # Placeholders
            r'aria-label="([^"]{1,120})"',  # ARIA labels
        ]

    def analyze_file_for_candidates(
        self,
        file_path: Path,
        intent_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze a single file for text improvement candidates.

        Args:
            file_path: Path to file to analyze
            intent_context: Optional context (e.g., "tighten labels for clarity")

        Returns:
            List of candidate proposals (not yet validated)
        """

        if not file_path.exists():
            return []

        # Only process UI files
        if file_path.suffix not in ['.tsx', '.ts', '.jsx', '.js']:
            return []

        # Skip test files and node_modules
        if 'test' in file_path.name.lower() or 'node_modules' in str(file_path):
            return []

        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception:
            return []

        candidates = []
        relative_path = str(file_path.relative_to(self.project_root))

        # Extract text nodes using patterns
        for pattern in self.text_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                text = match.group(1).strip()

                # Skip very short text (likely not labels)
                if len(text) < 3:
                    continue

                # Skip if already concise (heuristic)
                if len(text) <= 20 and not self._has_improvement_potential(text):
                    continue

                candidate = {
                    "file": relative_path,
                    "original_text": text,
                    "match_start": match.start(),
                    "match_end": match.end(),
                    "context": intent_context or "general UI clarity"
                }

                candidates.append(candidate)

        return candidates

    def _has_improvement_potential(self, text: str) -> bool:
        """Heuristic check if text could be improved."""

        # Check for common improvement signals
        improvement_signals = [
            len(text) > 60,  # Too verbose
            text.count(' ') > 8,  # Too many words
            'Self-Improvement' in text,  # Legacy naming
            'Panel' in text and len(text) > 25,  # Redundant "Panel"
            text.endswith('...'),  # Unclear truncation
        ]

        return any(improvement_signals)

    def generate_proposal(
        self,
        candidate: Dict[str, Any],
        use_llm: bool = True,
        confidence_override: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a proposal from a candidate.

        Args:
            candidate: Candidate dict from analyze_file_for_candidates
            use_llm: Whether to use LLM for rewriting (else use heuristics)
            confidence_override: Optional manual confidence score

        Returns:
            Proposal dict or None if generation fails
        """

        original_text = candidate["original_text"]
        file_path = candidate["file"]

        # Generate improved text
        if use_llm and self.llm_client:
            improved_text, confidence = self._llm_rewrite(original_text, candidate["context"])
        else:
            improved_text, confidence = self._heuristic_rewrite(original_text)

        if improved_text is None:
            return None

        # Use override confidence if provided
        if confidence_override is not None:
            confidence = confidence_override

        # Build proposal
        proposal = {
            "scope": "frontend",
            "file": file_path,
            "intent": f"Improve clarity: {candidate['context']}",
            "suggested_change": {
                "type": "text_replace",
                "before": original_text,
                "after": improved_text
            },
            "confidence": confidence,
            "source": "head_coach"
        }

        # Validate against guardrails
        is_valid, error = self.guardrails.validate_proposal(proposal, self.project_root)

        if not is_valid:
            # Log validation failure (in production, would go to telemetry)
            return None

        return proposal

    def _heuristic_rewrite(self, text: str) -> Tuple[Optional[str], float]:
        """
        Simple heuristic-based text improvement.

        Returns:
            (improved_text, confidence)
        """

        improved = text
        confidence = 0.75  # Base confidence for heuristics

        # Heuristic 1: Remove redundant "Panel" suffix if preceded by descriptive word
        if improved.endswith(' Panel') and len(improved.split()) >= 2:
            improved = improved[:-6].strip()
            confidence = 0.85

        # Heuristic 2: Shorten "Self-Improvement" to "Adaptive Learning"
        if 'Self-Improvement' in improved:
            improved = improved.replace('Self-Improvement', 'Adaptive Learning')
            confidence = 0.88

        # Heuristic 3: Remove trailing ellipsis and add proper text
        if improved.endswith('...'):
            improved = improved[:-3].strip()
            confidence = 0.80

        # Heuristic 4: Simplify verbose button text
        if len(improved) > 30 and any(word in improved.lower() for word in ['click', 'press', 'tap']):
            # Remove action verbs from button text (buttons are self-evident)
            improved = re.sub(r'\b(click|press|tap)\s+', '', improved, flags=re.IGNORECASE).strip()
            confidence = 0.82

        # If no changes made, return None
        if improved == text:
            return None, 0.0

        return improved, confidence

    def _llm_rewrite(self, text: str, context: str) -> Tuple[Optional[str], float]:
        """
        Use LLM to rewrite text within constraints.

        Returns:
            (improved_text, confidence)
        """

        if not self.llm_client:
            return self._heuristic_rewrite(text)

        prompt = f"""Rewrite this UI label to be more concise and clear:

Original: "{text}"
Context: {context}

Rules:
- Maximum 80 characters
- Concise, neutral language (no marketing speak)
- No exclamation marks
- Preserve key meaning

Return ONLY the improved label, nothing else."""

        try:
            response = self.llm_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            improved_text = response.content[0].text.strip()

            # Remove quotes if LLM added them
            improved_text = improved_text.strip('"\'')

            # Validate length
            if len(improved_text) > 80:
                return self._heuristic_rewrite(text)

            # Confidence based on how much improvement was made
            similarity = self._calculate_similarity(text, improved_text)
            if similarity > 0.9:
                # Too similar, not much improvement
                return self._heuristic_rewrite(text)

            confidence = 0.90  # High confidence for LLM rewrites

            return improved_text, confidence

        except Exception:
            # Fall back to heuristics on LLM failure
            return self._heuristic_rewrite(text)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity score between two texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def scan_directory_for_proposals(
        self,
        directory: Path,
        intent_context: str = "improve UI clarity",
        max_proposals: int = 10,
        use_llm: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Scan a directory for UI improvement opportunities.

        Args:
            directory: Directory to scan (relative to project_root)
            intent_context: Context for improvements
            max_proposals: Maximum proposals to generate
            use_llm: Whether to use LLM for rewriting

        Returns:
            List of valid proposals
        """

        full_path = self.project_root / directory
        if not full_path.exists() or not full_path.is_dir():
            return []

        proposals = []

        # Find all UI files
        ui_files = []
        for ext in ['.tsx', '.ts', '.jsx', '.js']:
            ui_files.extend(full_path.rglob(f'*{ext}'))

        # Analyze each file
        for file_path in ui_files[:20]:  # Limit to 20 files per scan
            candidates = self.analyze_file_for_candidates(file_path, intent_context)

            # Generate proposals from candidates
            for candidate in candidates[:3]:  # Max 3 per file
                proposal = self.generate_proposal(candidate, use_llm=use_llm)

                if proposal:
                    proposals.append(proposal)

                    if len(proposals) >= max_proposals:
                        return proposals

        return proposals

    def trigger_analysis_based_proposals(
        self,
        analysis_results: Dict[str, Any],
        max_proposals: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate proposals based on Self-Improvement analysis results.

        Args:
            analysis_results: Results from /learning/analyze endpoint
            max_proposals: Maximum proposals to generate

        Returns:
            List of proposals
        """

        proposals = []

        # Extract confusion signals from analysis
        confusion_modules = analysis_results.get("confusion_signals", {}).get("modules", [])

        for module in confusion_modules[:3]:  # Top 3 confused modules
            module_name = module.get("name", "")
            confusion_text = module.get("confused_text", [])

            # Determine directory to scan
            if "DevX" in module_name:
                directory = Path("devx/frontend/src")
            elif "ReDNA" in module_name:
                directory = Path("web/src")
            else:
                continue

            # Generate context from confusion
            context = f"address confusion: {', '.join(confusion_text[:2])}" if confusion_text else "improve clarity"

            # Scan directory
            module_proposals = self.scan_directory_for_proposals(
                directory,
                intent_context=context,
                max_proposals=max(2, max_proposals - len(proposals)),
                use_llm=True
            )

            proposals.extend(module_proposals)

            if len(proposals) >= max_proposals:
                break

        return proposals[:max_proposals]


def create_proposal_generator(
    project_root: Optional[Path] = None,
    guardrails_config: Optional[Dict[str, Any]] = None,
    llm_client: Optional[Any] = None  # anthropic.Anthropic if available
) -> ProposalGenerator:
    """Factory function to create ProposalGenerator instance."""
    return ProposalGenerator(project_root, guardrails_config, llm_client)
