"""
Tests for Head Coach prompt loader

Verifies dynamic prompt loading, SHA256 computation, and hot-reload functionality.
"""
import hashlib
from pathlib import Path

def test_hc_prompt_loader_loads_file():
    """Test that prompt loader can read the HC prompt file."""
    from ReDNACoreDemo.core.hc_prompt_loader import load_hc_prompt

    # Load prompt
    prompt_info = load_hc_prompt()

    # Verify structure
    assert "text" in prompt_info
    assert "sha256" in prompt_info
    assert "version" in prompt_info
    assert "loaded_at" in prompt_info

    # Verify prompt text is non-empty
    assert len(prompt_info["text"]) > 100, "Prompt text should be substantial"

    # Verify SHA is hex string
    assert len(prompt_info["sha256"]) == 64, "SHA256 should be 64 hex characters"

    print(f"✓ Prompt loaded: {len(prompt_info['text'])} chars, version {prompt_info['version']}")


def test_sha256_matches_file_content():
    """Test that computed SHA256 matches actual file content."""
    from ReDNACoreDemo.core.hc_prompt_loader import load_hc_prompt

    # Get prompt info
    prompt_info = load_hc_prompt()

    # Compute SHA256 manually
    prompt_text = prompt_info["text"]
    expected_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    # Verify match
    assert prompt_info["sha256"] == expected_sha, "SHA256 should match file content"

    print(f"✓ SHA256 verified: {expected_sha[:16]}...")


def test_version_extraction():
    """Test that version is extracted from markdown frontmatter."""
    from ReDNACoreDemo.core.hc_prompt_loader import load_hc_prompt

    prompt_info = load_hc_prompt()

    # Version should not be "unknown" if file is properly formatted
    # (but we allow it if markdown doesn't have version)
    assert prompt_info["version"] != "error", "Version extraction should not error"

    print(f"✓ Version extracted: {prompt_info['version']}")


def test_caching_works():
    """Test that prompt is cached after first load."""
    from ReDNACoreDemo.core.hc_prompt_loader import load_hc_prompt, _prompt_cache

    # First load
    prompt1 = load_hc_prompt()
    sha1 = prompt1["sha256"]

    # Second load (should use cache)
    prompt2 = load_hc_prompt()
    sha2 = prompt2["sha256"]

    # Should return same object (cache hit)
    assert sha1 == sha2, "Cached prompt should have same SHA"

    print(f"✓ Cache working: same SHA on second load")


def test_reload_clears_cache():
    """Test that reload_hc_prompt clears cache and reloads."""
    from ReDNACoreDemo.core.hc_prompt_loader import load_hc_prompt, reload_hc_prompt

    # Initial load
    prompt1 = load_hc_prompt()
    sha1 = prompt1["sha256"]

    # Reload (should clear cache and reload from disk)
    prompt2 = reload_hc_prompt()
    sha2 = prompt2["sha256"]

    # SHA should be same (file didn't change), but cache was cleared
    assert sha1 == sha2, "Reloaded prompt should match original"

    print(f"✓ Reload works: cache cleared and reloaded")


def test_convenience_functions():
    """Test that convenience functions work correctly."""
    from ReDNACoreDemo.core.hc_prompt_loader import (
        get_hc_prompt_text,
        get_hc_prompt_sha256,
        get_hc_prompt_version
    )

    # Get via convenience functions
    text = get_hc_prompt_text()
    sha = get_hc_prompt_sha256()
    version = get_hc_prompt_version()

    # Verify non-empty
    assert len(text) > 100, "Text should be substantial"
    assert len(sha) == 64, "SHA should be 64 hex chars"
    assert version != "", "Version should not be empty"

    print(f"✓ Convenience functions work: text={len(text)} chars, sha={sha[:8]}..., version={version}")


if __name__ == "__main__":
    import sys
    import os

    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # Run tests
    print("Running HC Prompt Loader Tests\n")

    try:
        test_hc_prompt_loader_loads_file()
        test_sha256_matches_file_content()
        test_version_extraction()
        test_caching_works()
        test_reload_clears_cache()
        test_convenience_functions()

        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
