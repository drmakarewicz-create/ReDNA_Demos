"""Render Coach - PaDNA render manifest and delta loop utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ReDNACoreDemo.core.photo_coach import get_user_media_paths, generate_batch_id


def create_render_manifest(
    user_id: str,
    base_dir: Path,
    traits_resolved_path: str,
    images_batch_id: Optional[str] = None,
    workflow: str = "comfyui/realvisxl.json",
    seed: int = 12345,
    prompt: str = "",
    render_batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a render manifest for a PaDNA render batch.

    Args:
        user_id: User identifier
        base_dir: Base directory for data storage
        traits_resolved_path: Path to resolved state JSON
        images_batch_id: Photo batch ID used as reference
        workflow: ComfyUI workflow identifier
        seed: Random seed
        prompt: Generated or manual prompt
        render_batch_id: Optional render batch ID

    Returns:
        Render manifest dictionary
    """
    paths = get_user_media_paths(user_id, base_dir)

    # Generate render batch ID if not provided
    timestamp = datetime.now(timezone.utc)
    if render_batch_id is None:
        render_batch_id = generate_batch_id(user_id, timestamp)

    # Create render directory
    render_dir = paths["renders"] / render_batch_id
    render_dir.mkdir(parents=True, exist_ok=True)

    # Build manifest
    manifest = {
        "user_id": user_id,
        "render_batch_id": render_batch_id,
        "created_at": timestamp.isoformat(),
        "inputs": {
            "traits_resolved_path": traits_resolved_path,
            "images_batch_id": images_batch_id,
            "workflow": workflow,
            "seed": seed,
            "prompt": prompt,
        },
        "outputs": {
            "render": f"renders/{render_batch_id}/render.png",
            "side_by_side": f"renders/{render_batch_id}/comp_side_by_side.png",
        },
    }

    # Save manifest
    manifest_path = render_dir / "render_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Append to journal
    journal_date = timestamp.strftime("%Y-%m-%d")
    journal_path = paths["hc_journal"] / f"{journal_date}.md"
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    with open(journal_path, "a", encoding="utf-8") as f:
        f.write(f"\n## {timestamp.strftime('%H:%M:%S')} - Render Created\n\n")
        f.write(f"- Render Batch ID: `{render_batch_id}`\n")
        f.write(f"- Workflow: `{workflow}`\n")
        f.write(f"- Seed: {seed}\n")
        if images_batch_id:
            f.write(f"- Reference Images: `{images_batch_id}`\n")
        f.write(f"- Prompt: {prompt[:100]}...\n\n" if len(prompt) > 100 else f"- Prompt: {prompt}\n\n")

    return manifest


def list_render_batches(user_id: str, base_dir: Path) -> List[Dict[str, Any]]:
    """List all render batches for a user (sorted descending by created_at)."""
    paths = get_user_media_paths(user_id, base_dir)
    renders_dir = paths["renders"]

    if not renders_dir.exists():
        return []

    batches = []

    for render_batch_dir in renders_dir.iterdir():
        if not render_batch_dir.is_dir():
            continue

        manifest_path = render_batch_dir / "render_manifest.json"
        if not manifest_path.exists():
            continue

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            batches.append({
                "render_batch_id": manifest.get("render_batch_id"),
                "created_at": manifest.get("created_at"),
                "workflow": manifest.get("inputs", {}).get("workflow"),
            })
        except Exception as e:
            print(f"Warning: Could not read render manifest {manifest_path}: {e}")
            continue

    # Sort by created_at descending
    batches.sort(key=lambda b: b.get("created_at", ""), reverse=True)

    return batches


def get_render_batch(user_id: str, render_batch_id: str, base_dir: Path) -> Optional[Dict[str, Any]]:
    """Get a specific render batch manifest."""
    paths = get_user_media_paths(user_id, base_dir)
    manifest_path = paths["renders"] / render_batch_id / "render_manifest.json"

    if not manifest_path.exists():
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_render_id(user_id: str, base_dir: Path) -> Optional[str]:
    """Get the most recent render batch ID for a user."""
    batches = list_render_batches(user_id, base_dir)

    if not batches:
        return None

    return batches[0]["render_batch_id"]


def get_render_stats(user_id: str, base_dir: Path) -> Dict[str, Any]:
    """Get render statistics for a user."""
    batches = list_render_batches(user_id, base_dir)

    latest_render_id = batches[0]["render_batch_id"] if batches else None

    return {
        "batches": len(batches),
        "latest_render_id": latest_render_id,
    }


def analyze_photo_render_delta(
    user_id: str,
    photo_batch_id: str,
    render_batch_id: str,
    base_dir: Path,
) -> Dict[str, Any]:
    """
    Analyze delta between photo batch and render batch.

    This is a heuristic analysis to identify missing traits or adjustments needed.

    Returns:
        Dictionary with delta analysis and recommendations
    """
    from ReDNACoreDemo.core.photo_coach import get_photo_batch

    photo_batch = get_photo_batch(user_id, photo_batch_id, base_dir)
    render_batch = get_render_batch(user_id, render_batch_id, base_dir)

    if not photo_batch or not render_batch:
        return {"error": "Batch not found"}

    # Collect all labels from photo batch
    all_labels = set()
    for image in photo_batch.get("images", []):
        all_labels.update(image.get("labels", []))

    # Heuristics for delta detection
    recommendations = []

    # Check for freckles
    if "freckles?" in all_labels or "freckles" in all_labels:
        recommendations.append({
            "trait": "PaDNA.SkinDNA.Freckles.Density",
            "action": "add_evidence",
            "reason": "Freckles detected in photos but may not be in resolved state",
            "priority": 5,
        })

    # Check for skin tone
    skin_tone_labels = [label for label in all_labels if "skin_tone" in label.lower()]
    if skin_tone_labels:
        recommendations.append({
            "trait": "PaDNA.SkinDNA.SkinTone.Base",
            "action": "verify_evidence",
            "reason": f"Skin tone indicators found: {', '.join(skin_tone_labels)}",
            "priority": 4,
        })

    # Check for portrait/face
    if "face" in all_labels or "portrait" in all_labels:
        recommendations.append({
            "trait": "PaDNA.FacialDNA.FaceShape.Overall",
            "action": "add_evidence",
            "reason": "Face/portrait detected - verify facial traits",
            "priority": 3,
        })

    return {
        "photo_batch_id": photo_batch_id,
        "render_batch_id": render_batch_id,
        "photo_labels": list(all_labels),
        "recommendations": recommendations,
        "delta_count": len(recommendations),
    }
