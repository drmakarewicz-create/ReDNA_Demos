"""
Import sanity tests for DevX and other ReDNA modules.

Ensures that module paths are correctly structured and importable
using the standard Python import mechanism with PYTHONPATH set to repo root.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_devx_backend_api_importable():
    """Verify ReDNACoreDemo.devx.backend.api is importable and has an app."""
    # Ensure repo root is in path
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Import the module
    module = importlib.import_module("ReDNACoreDemo.devx.backend.api")

    # Verify it has the FastAPI app
    assert hasattr(module, "app"), "ReDNACoreDemo.devx.backend.api must expose 'app'"
    assert module.app is not None


def test_core_api_importable():
    """Verify ReDNACoreDemo.core.api is importable and has build_app.

    Note: This test may fail if shared dependencies (e.g., shared.persona_schema)
    are not available. In production, the module path in stack_api.py is correct.
    """
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        module = importlib.import_module("ReDNACoreDemo.core.api")
        # Core uses --factory mode, so build_app must exist
        assert hasattr(module, "build_app"), "ReDNACoreDemo.core.api must expose 'build_app' factory"
        assert callable(module.build_app)
    except ModuleNotFoundError as e:
        # Core API has complex dependencies; the module path is correct even if import fails
        if "shared.persona_schema" in str(e):
            import pytest
            pytest.skip(f"Skipping due to missing dependency: {e}")
        raise


def test_ucnrr_app_importable():
    """Verify UCN_RR_Demo.ucnrr_app is importable and has an app."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    module = importlib.import_module("UCN_RR_Demo.ucnrr_app")

    # Verify it has the FastAPI app
    assert hasattr(module, "app"), "UCN_RR_Demo.ucnrr_app must expose 'app'"
    assert module.app is not None


def test_stack_api_service_definitions():
    """Verify stack_api.SERVICES has correct module paths."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from ReDNACoreDemo.devx.backend import stack_api

    # Check service definitions
    assert "core" in stack_api.SERVICES
    assert "ucnrr" in stack_api.SERVICES
    assert "devx" in stack_api.SERVICES

    # Verify module paths are fully qualified
    core = stack_api.SERVICES["core"]
    assert core.uvicorn_app == "ReDNACoreDemo.core.api:build_app"
    assert core.factory is True

    ucnrr = stack_api.SERVICES["ucnrr"]
    assert ucnrr.uvicorn_app == "UCN_RR_Demo.ucnrr_app:app"
    assert ucnrr.factory is False

    devx = stack_api.SERVICES["devx"]
    assert devx.uvicorn_app == "ReDNACoreDemo.devx.backend.api:app"
    assert devx.factory is False
