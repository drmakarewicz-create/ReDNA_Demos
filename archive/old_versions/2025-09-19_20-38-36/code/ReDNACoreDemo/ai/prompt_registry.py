# ai/prompt_registry.py
from __future__ import annotations
import json, re
from pathlib import Path
from typing import Dict, Any, Optional

ROOT = Path(__file__).resolve().parent.parent  # repo root (next to app.py)
PROMPTS_DIR = ROOT / "prompts"                 # e.g. prompts/ucn_rr/*.md

def load_prompt(key: str, variant: str = "default") -> str:
    """
    key examples:
      'ucn_rr/confidence'
      'core/propagation'
      'head_coach/system'
      'coaches/bucket_list'
    Will look for: prompts/<key>[@variant].md  (e.g. prompts/ucn_rr/confidence@default.md)
    Fallback to prompts/<key>.md if variant missing.
    """
    safe = key.strip("/").replace("..", "")
    base = PROMPTS_DIR / (safe + f"@{variant}.md")
    if base.exists(): return base.read_text(encoding="utf-8")
    alt = PROMPTS_DIR / (safe + ".md")
    if alt.exists(): return alt.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt not found: {key} (variant={variant})")

def fill(template: str, **vars) -> str:
    s = template
    for k, v in vars.items():
        s = s.replace("{"+k+"}", str(v))
    return s