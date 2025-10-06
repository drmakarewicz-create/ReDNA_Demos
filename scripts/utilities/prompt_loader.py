# prompt_loader.py
from pathlib import Path
from typing import Optional

def load_prompts(*names: str, base_dir: Optional[Path] = None) -> str:
    """
    Concatenate prompt .md files in order.
    - base_dir defaults to ./prompts relative to CWD.
    - Missing files are tolerated and noted in the combined text.
    """
    root = base_dir or (Path.cwd() / "prompts")
    chunks: list[str] = []
    for n in names:
        p = root / n
        try:
            chunks.append(p.read_text(encoding="utf-8"))
        except Exception:
            chunks.append(f"# Missing prompt: {n}\n")
    return "\n\n---\n\n".join(chunks)