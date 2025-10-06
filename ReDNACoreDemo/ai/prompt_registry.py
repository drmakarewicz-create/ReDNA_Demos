"""Runtime prompt registry for personas and core prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"


@dataclass(slots=True)
class PromptBundle:
    """Group of prompt assets for a persona."""

    system: str
    dialogue_templates: List[str] = field(default_factory=list)
    micro_actions: List[str] = field(default_factory=list)
    evaluations: List[str] = field(default_factory=list)


_PERSONA_BUNDLES: Dict[str, PromptBundle] = {}


_DEFAULT_PERSONA_ASSETS: Dict[str, Dict[str, str]] = {
    "relationship_coach": {
        "system.md": """Voice: warm, plain, human. Keep sentences short. Use \"you\", not labels like \"introverted individual\".
No internal jargon (no RR/UCN, \"data points\", \"path=\", etc.).
Always translate traits into natural language, e.g. \"you recharge solo\" not \"introvert\".
Offer one focused next step at a time (\"micro-action\").
Ask one question max per turn.
""",
        "opening.md": """Hi — I’m your Relationship Coach. I help with honest conversations, repair moves, and tiny experiments that build connection.
We can start with a quick snapshot or jump straight to one small step you can try today. Which do you prefer?
""",
        "microactions.md": """• Send a 2-line appreciation text naming one specific thing you liked from today.
• Ask a curious \"how\" or \"what\" question and give 30 seconds of quiet after they answer.
• Share one boundary in one sentence; offer one alternative that still honors it.
""",
    }
}


def _normalize_relative(path_str: str) -> Path:
    """Return an absolute path rooted at the repo, rejecting escapes."""
    candidate = Path(path_str)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:  # pragma: no cover - defensive
        raise FileNotFoundError(f"Asset path escapes repo root: {resolved}") from exc
    return resolved


def resolve_asset_path(path_str: str) -> Path:
    """Resolve a possibly-relative asset path to an absolute repo path."""
    return _normalize_relative(path_str)


def read_asset(path_str: str) -> str:
    path = resolve_asset_path(path_str)
    if not path.exists():
        raise FileNotFoundError(
            f"Asset not found: {path_str} (resolved={path}, cwd={Path.cwd()})"
        )
    return path.read_text(encoding="utf-8")


def load_prompt(key: str, variant: str = "default") -> str:
    """Load a prompt stored under the global prompts directory."""
    safe = key.strip("/").replace("..", "")
    candidate_with_variant = PROMPTS_DIR / f"{safe}@{variant}.md"
    if candidate_with_variant.exists():
        return candidate_with_variant.read_text(encoding="utf-8")
    candidate = PROMPTS_DIR / f"{safe}.md"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "Prompt not found: {key} (variant={variant}) -> attempted {cw} and {c}. cwd={cwd}".format(
            key=key,
            variant=variant,
            cw=candidate_with_variant,
            c=candidate,
            cwd=Path.cwd(),
        )
    )


def load_templates(paths: Iterable[str]) -> List[str]:
    return [read_asset(path) for path in paths]


def register_persona_bundle(persona_id: str, bundle: PromptBundle) -> None:
    """Register or replace the prompt bundle for a persona."""
    safe_id = persona_id.strip()
    if not safe_id:
        raise ValueError("persona_id cannot be empty")
    _PERSONA_BUNDLES[safe_id] = PromptBundle(
        system=bundle.system,
        dialogue_templates=list(bundle.dialogue_templates),
        micro_actions=list(bundle.micro_actions),
        evaluations=list(bundle.evaluations),
    )

    try:  # pragma: no cover - UI cache invalidation guarded
        from ExplorerFinal.ui import persona_router  # type: ignore

        persona_router.load_personas.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass


def get_persona_bundle(persona_id: str) -> Optional[PromptBundle]:
    return _PERSONA_BUNDLES.get(persona_id)


def list_persona_bundles() -> Dict[str, PromptBundle]:
    return dict(_PERSONA_BUNDLES)


def ensure_persona_assets(persona_id: str) -> List[Path]:
    defaults = _DEFAULT_PERSONA_ASSETS.get(persona_id)
    if defaults is None:
        raise KeyError(f"No default assets registered for persona '{persona_id}'")
    folder = PROMPTS_DIR / persona_id
    folder.mkdir(parents=True, exist_ok=True)
    created: List[Path] = []
    for filename, content in defaults.items():
        path = folder / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(path)
    return created


def fill(template: str, **vars) -> str:
    s = template
    for k, v in vars.items():
        s = s.replace("{" + k + "}", str(v))
    return s


# Shared safety preamble for all personas
SAFETY_PREAMBLE = """You are a helpful AI assistant. Follow these safety guidelines:
- Never provide medical, legal, or financial advice
- If asked about harmful activities, politely decline and suggest safer alternatives
- Respect user privacy and never ask for sensitive personal information
- Be honest about your limitations as an AI
"""


def get_persona_system_prompt(persona_id: str, include_safety: bool = True) -> Optional[str]:
    """Get the system prompt for a persona, optionally with safety preamble."""
    bundle = get_persona_bundle(persona_id)
    if not bundle:
        return None

    if include_safety:
        return f"{SAFETY_PREAMBLE}\n\n{bundle.system}"
    return bundle.system


def get_default_system_prompt(persona_id: str) -> str:
    """Get a default system prompt for a persona if not registered."""
    defaults = {
        "head_coach": """You are the Head Coach - the central orchestrator of the ReDNA system.
Your role is to coordinate between different specialized coaches and guide the user's journey.
Keep responses concise and action-oriented. Focus on what the user can do next.""",

        "rc": """You are the Relationship Coach (RC).
Help users improve their relationships through honest conversations and small, actionable experiments.
Use warm, plain language. Keep sentences short. Offer one focused next step at a time.""",

        "photo": """You are the Photo Coach.
Analyze photos to extract visual traits and provide feedback on appearance-related attributes.
Be objective and constructive. Focus on what you observe, not judgments.""",

        "rendering": """You are the Rendering Coach (formerly PaDNA Coach).
Help users visualize and create personalized avatars based on their traits.
Explain rendering decisions and suggest refinements.""",
    }

    prompt = defaults.get(persona_id, defaults["head_coach"])
    return f"{SAFETY_PREAMBLE}\n\n{prompt}"


__all__ = [
    "PromptBundle",
    "PROMPTS_DIR",
    "REPO_ROOT",
    "SAFETY_PREAMBLE",
    "ensure_persona_assets",
    "fill",
    "get_default_system_prompt",
    "get_persona_bundle",
    "get_persona_system_prompt",
    "list_persona_bundles",
    "load_prompt",
    "load_templates",
    "read_asset",
    "register_persona_bundle",
    "resolve_asset_path",
]
