"""Photo Coach - Image ingestion and manifest management."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from PIL.ExifTags import TAGS

THUMB_SIZE = (512, 512)
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}


def get_user_media_paths(user_id: str, base_dir: Path) -> Dict[str, Path]:
    """Get all media-related paths for a user."""
    user_root = base_dir / "data" / "users" / user_id

    return {
        "media_root": user_root / "media",
        "images": user_root / "media" / "images",
        "thumbs": user_root / "media" / "thumbs",
        "manifests": user_root / "media" / "manifests",
        "renders": user_root / "renders",
        "hc_journal": user_root / "hc" / "journal",
        "hc_plans": user_root / "hc" / "plans",
        "state": user_root / "state",
    }


def ensure_media_dirs(user_id: str, base_dir: Path) -> None:
    """Ensure all media directories exist for a user."""
    paths = get_user_media_paths(user_id, base_dir)

    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def generate_batch_id(user_id: str, timestamp: Optional[datetime] = None) -> str:
    """Generate a batch ID in format: YYYY-MM-DDThh-mm-ss-<user_id>."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    # Format: 2025-10-04T12-00-00-LLTEST
    return f"{timestamp.strftime('%Y-%m-%dT%H-%M-%S')}-{user_id}"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def extract_exif(image_path: Path) -> Dict[str, Any]:
    """Extract EXIF metadata from an image."""
    exif_data = {}

    try:
        with Image.open(image_path) as img:
            exif = img.getexif()

            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)

                    # Extract commonly used fields
                    if tag == "DateTime":
                        exif_data["datetime"] = str(value)
                    elif tag == "FocalLength":
                        if isinstance(value, tuple):
                            exif_data["focal_length"] = value[0] / value[1] if value[1] != 0 else 0
                        else:
                            exif_data["focal_length"] = float(value)
                    elif tag == "ISOSpeedRatings":
                        exif_data["iso"] = int(value)
                    elif tag == "Make":
                        exif_data["camera_make"] = str(value)
                    elif tag == "Model":
                        exif_data["camera_model"] = str(value)

    except Exception as e:
        # Non-fatal, just return empty dict
        print(f"Warning: Could not extract EXIF from {image_path}: {e}")

    return exif_data


def create_thumbnail(source_path: Path, thumb_path: Path, size: Tuple[int, int] = THUMB_SIZE) -> None:
    """Create a thumbnail of an image."""
    thumb_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as img:
        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background

        # Create thumbnail maintaining aspect ratio
        img.thumbnail(size, Image.Resampling.LANCZOS)

        # Save as JPEG
        img.save(thumb_path, "JPEG", quality=85, optimize=True)


def ingest_photo_batch(
    user_id: str,
    files: List[Tuple[str, bytes]],  # List of (filename, content)
    base_dir: Path,
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingest a batch of photos for a user.

    Args:
        user_id: User identifier
        files: List of (filename, file_content) tuples
        base_dir: Base directory for data storage
        batch_id: Optional batch ID (auto-generated if not provided)

    Returns:
        Batch manifest dictionary
    """
    # Ensure directories exist
    ensure_media_dirs(user_id, base_dir)
    paths = get_user_media_paths(user_id, base_dir)

    # Generate batch ID if not provided
    timestamp = datetime.now(timezone.utc)
    if batch_id is None:
        batch_id = generate_batch_id(user_id, timestamp)

    # Create batch directories
    batch_images_dir = paths["images"] / batch_id
    batch_thumbs_dir = paths["thumbs"] / batch_id
    batch_images_dir.mkdir(parents=True, exist_ok=True)
    batch_thumbs_dir.mkdir(parents=True, exist_ok=True)

    # Process each image
    images_metadata = []

    for filename, content in files:
        # Validate file extension
        file_path = Path(filename)
        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            continue

        # Save original
        original_path = batch_images_dir / filename
        original_path.write_bytes(content)

        # Create thumbnail
        thumb_filename = file_path.stem + ".jpg"
        thumb_path = batch_thumbs_dir / thumb_filename
        create_thumbnail(original_path, thumb_path)

        # Extract metadata
        hash_sha256 = compute_sha256(original_path)
        exif = extract_exif(original_path)

        # Get image dimensions
        with Image.open(original_path) as img:
            width, height = img.size

        # Build image metadata
        image_meta = {
            "filename": filename,
            "path": f"media/images/{batch_id}/{filename}",
            "thumb": f"media/thumbs/{batch_id}/{thumb_filename}",
            "hash_sha256": hash_sha256,
            "width": width,
            "height": height,
            "exif": exif,
            "labels": [],
            "notes": "",
        }

        images_metadata.append(image_meta)

    # Create manifest
    manifest = {
        "user_id": user_id,
        "batch_id": batch_id,
        "created_at": timestamp.isoformat(),
        "count": len(images_metadata),
        "images": images_metadata,
    }

    # Save manifest
    manifest_path = paths["manifests"] / f"{batch_id}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Append to journal
    journal_date = timestamp.strftime("%Y-%m-%d")
    journal_path = paths["hc_journal"] / f"{journal_date}.md"
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    with open(journal_path, "a", encoding="utf-8") as f:
        f.write(f"\n## {timestamp.strftime('%H:%M:%S')} - Photo Batch Ingested\n\n")
        f.write(f"- Batch ID: `{batch_id}`\n")
        f.write(f"- Images: {len(images_metadata)}\n")
        f.write(f"- Location: `media/images/{batch_id}/`\n\n")

    return manifest


def list_photo_batches(user_id: str, base_dir: Path) -> List[Dict[str, Any]]:
    """List all photo batches for a user (sorted descending by created_at)."""
    paths = get_user_media_paths(user_id, base_dir)
    manifests_dir = paths["manifests"]

    if not manifests_dir.exists():
        return []

    batches = []

    for manifest_file in manifests_dir.glob("*.json"):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            batches.append({
                "batch_id": manifest.get("batch_id"),
                "created_at": manifest.get("created_at"),
                "count": manifest.get("count", 0),
            })
        except Exception as e:
            print(f"Warning: Could not read manifest {manifest_file}: {e}")
            continue

    # Sort by created_at descending
    batches.sort(key=lambda b: b.get("created_at", ""), reverse=True)

    return batches


def get_photo_batch(user_id: str, batch_id: str, base_dir: Path) -> Optional[Dict[str, Any]]:
    """Get a specific photo batch manifest."""
    paths = get_user_media_paths(user_id, base_dir)
    manifest_path = paths["manifests"] / f"{batch_id}.json"

    if not manifest_path.exists():
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_vision_labels_stub(
    user_id: str,
    batch_id: str,
    base_dir: Path,
    image_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add mock vision labels to images in a batch.

    This is a stub implementation until vision LLM is integrated.
    """
    manifest = get_photo_batch(user_id, batch_id, base_dir)

    if not manifest:
        raise ValueError(f"Batch {batch_id} not found for user {user_id}")

    # Mock labels to add
    mock_labels = ["face", "portrait", "freckles?", "skin_tone_medium"]

    # Update labels for specific image or all images
    updated_count = 0

    for image in manifest["images"]:
        if image_filename is None or image["filename"] == image_filename:
            # Add mock labels if not already present
            existing_labels = set(image.get("labels", []))
            new_labels = [label for label in mock_labels if label not in existing_labels]

            if new_labels:
                image["labels"] = list(existing_labels) + new_labels
                updated_count += 1

    # Save updated manifest
    paths = get_user_media_paths(user_id, base_dir)
    manifest_path = paths["manifests"] / f"{batch_id}.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return {
        "batch_id": batch_id,
        "updated_images": updated_count,
        "labels_added": mock_labels,
    }


def get_latest_batch_id(user_id: str, base_dir: Path) -> Optional[str]:
    """Get the most recent batch ID for a user."""
    batches = list_photo_batches(user_id, base_dir)

    if not batches:
        return None

    return batches[0]["batch_id"]


def get_media_stats(user_id: str, base_dir: Path) -> Dict[str, Any]:
    """Get media statistics for a user."""
    batches = list_photo_batches(user_id, base_dir)

    total_images = sum(batch.get("count", 0) for batch in batches)
    latest_batch_id = batches[0]["batch_id"] if batches else None

    return {
        "batches": len(batches),
        "images_total": total_images,
        "latest_batch_id": latest_batch_id,
    }
