#!/usr/bin/env python3
"""
Photo Coach Acceptance Tests
Tests photo ingestion, batches, and vision labeling stub
"""

import io
import json
import os
import shutil
import time
from pathlib import Path

import pytest
import requests
from PIL import Image

CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8001")
TEST_USER = "PHOTO_TEST"


def cleanup_test_user():
    """Clean up test user data."""
    user_dir = Path("data/users") / TEST_USER
    if user_dir.exists():
        shutil.rmtree(user_dir)


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test."""
    cleanup_test_user()
    yield
    cleanup_test_user()


def create_test_image(filename: str, size=(800, 600), color=(255, 0, 0)) -> bytes:
    """Create a test image in memory."""
    img = Image.new('RGB', size, color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


def test_ingest_creates_manifest_and_thumbs():
    """Test 1: POST /photo/ingest creates manifest and thumbnails."""
    print(f"\n=== Test 1: Photo Ingest (user={TEST_USER}) ===")

    # Create test images
    image1 = create_test_image("test1.jpg", color=(255, 0, 0))
    image2 = create_test_image("test2.jpg", color=(0, 255, 0))

    # Upload images
    files = [
        ('files', ('test1.jpg', image1, 'image/jpeg')),
        ('files', ('test2.jpg', image2, 'image/jpeg')),
    ]

    response = requests.post(
        f"{CORE_API_URL}/photo/ingest",
        params={"user_id": TEST_USER},
        files=files
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    manifest = response.json()
    print(f"  ✓ Manifest created: batch_id={manifest['batch_id']}")

    # Verify manifest structure
    assert manifest["user_id"] == TEST_USER
    assert manifest["count"] == 2
    assert len(manifest["images"]) == 2

    # Verify files exist
    user_dir = Path("data/users") / TEST_USER
    batch_id = manifest["batch_id"]

    for img in manifest["images"]:
        # Check original
        orig_path = user_dir / img["path"]
        assert orig_path.exists(), f"Original not found: {orig_path}"

        # Check thumbnail
        thumb_path = user_dir / img["thumb"]
        assert thumb_path.exists(), f"Thumbnail not found: {thumb_path}"

        # Verify thumbnail is smaller
        with Image.open(thumb_path) as thumb_img:
            assert thumb_img.width <= 512 and thumb_img.height <= 512

        print(f"  ✓ Image: {img['filename']} (hash: {img['hash_sha256'][:16]}...)")

    # Verify manifest file exists
    manifest_file = user_dir / "media" / "manifests" / f"{batch_id}.json"
    assert manifest_file.exists()

    print(f"  ✓ Test 1 passed")


def test_list_batches_returns_latest_first():
    """Test 2: GET /photo/batches returns batches sorted by created_at desc."""
    print(f"\n=== Test 2: List Batches (user={TEST_USER}) ===")

    # Create two batches
    for i in range(2):
        image = create_test_image(f"batch{i}.jpg")
        files = [('files', (f'batch{i}.jpg', image, 'image/jpeg'))]

        requests.post(
            f"{CORE_API_URL}/photo/ingest",
            params={"user_id": TEST_USER},
            files=files
        )
        time.sleep(1.1)  # Ensure different timestamps (batch IDs have 1-second precision)

    # List batches
    response = requests.get(
        f"{CORE_API_URL}/photo/batches",
        params={"user_id": TEST_USER}
    )

    assert response.status_code == 200
    data = response.json()
    batches = data["batches"]

    assert len(batches) == 2
    print(f"  ✓ Found {len(batches)} batches")

    # Verify descending order
    assert batches[0]["created_at"] > batches[1]["created_at"], "Batches not sorted descending"

    for batch in batches:
        print(f"    - {batch['batch_id']}: {batch['count']} images at {batch['created_at']}")

    print(f"  ✓ Test 2 passed")


def test_get_batch_returns_manifest():
    """Test 3: GET /photo/batch returns full manifest."""
    print(f"\n=== Test 3: Get Batch (user={TEST_USER}) ===")

    # Create batch
    image = create_test_image("test.jpg")
    files = [('files', ('test.jpg', image, 'image/jpeg'))]

    ingest_response = requests.post(
        f"{CORE_API_URL}/photo/ingest",
        params={"user_id": TEST_USER},
        files=files
    )

    batch_id = ingest_response.json()["batch_id"]

    # Get batch
    response = requests.get(
        f"{CORE_API_URL}/photo/batch",
        params={"user_id": TEST_USER, "batch_id": batch_id}
    )

    assert response.status_code == 200
    manifest = response.json()

    assert manifest["batch_id"] == batch_id
    assert manifest["count"] == 1
    assert len(manifest["images"]) == 1

    img = manifest["images"][0]
    assert "hash_sha256" in img
    assert "width" in img
    assert "height" in img

    print(f"  ✓ Batch manifest: {batch_id}")
    print(f"    - Images: {manifest['count']}")
    print(f"    - SHA256: {img['hash_sha256'][:16]}...")
    print(f"  ✓ Test 3 passed")


def test_vision_stub_adds_labels():
    """Test 4: POST /photo/vision/label adds mock labels."""
    print(f"\n=== Test 4: Vision Stub (user={TEST_USER}) ===")

    # Create batch
    image = create_test_image("portrait.jpg")
    files = [('files', ('portrait.jpg', image, 'image/jpeg'))]

    ingest_response = requests.post(
        f"{CORE_API_URL}/photo/ingest",
        params={"user_id": TEST_USER},
        files=files
    )

    batch_id = ingest_response.json()["batch_id"]

    # Apply vision labels
    response = requests.post(
        f"{CORE_API_URL}/photo/vision/label",
        params={"user_id": TEST_USER, "batch_id": batch_id}
    )

    assert response.status_code == 200
    result = response.json()

    assert result["batch_id"] == batch_id
    assert result["updated_images"] > 0
    assert len(result["labels_added"]) > 0

    print(f"  ✓ Labels added: {result['labels_added']}")

    # Verify labels in manifest
    batch_response = requests.get(
        f"{CORE_API_URL}/photo/batch",
        params={"user_id": TEST_USER, "batch_id": batch_id}
    )

    manifest = batch_response.json()
    labels = manifest["images"][0]["labels"]

    assert len(labels) > 0, "No labels found in manifest"
    print(f"  ✓ Manifest labels: {labels}")
    print(f"  ✓ Test 4 passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
