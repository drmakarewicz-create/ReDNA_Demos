"""
Test Suite — Jarvis-Codex Phase 2

Validates auto-review pipeline, multi-file bundles, atomic rollback,
API payload enhancements, and token guardrails.
"""

from __future__ import annotations

import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

from ReDNACoreDemo.core.jarvis_codex.codex_agent import create_codex_agent, CodexAgent


# ============================================================================
# Fixtures / Helpers
# ============================================================================


@pytest.fixture
def phase2_project_root(tmp_path: Path) -> Path:
    """
    Build a temporary project structure matching Codex expectations.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()

    web_components = project_root / "web" / "src" / "components"
    web_components.mkdir(parents=True)

    # Prompts/insights directory for logs
    (project_root / "prompts" / "insights").mkdir(parents=True)

    return project_root


def write_component(project_root: Path, relative: str, content: str) -> Path:
    """Utility to create a TSX component under web/src/components."""
    target = project_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content).strip())
    return target


def load_file(project_root: Path, relative: str) -> str:
    return (project_root / relative).read_text()


def create_agent_for(root: Path) -> CodexAgent:
    return create_codex_agent(project_root=root)


# ============================================================================
# Auto-Review + Semantic Operations
# ============================================================================


def test_rename_prop_auto_review_passes(phase2_project_root: Path):
    """
    rename_prop should pass auto-review and apply cleanly.
    Verifies AST parse check and manifest stats.
    """
    component_path = "web/src/components/Card.tsx"
    write_component(
        phase2_project_root,
        component_path,
        """
        export function CardDemo() {
          return (
            <Card title="Hello World">
              <p>Body</p>
            </Card>
          );
        }
        """,
    )

    agent = create_agent_for(phase2_project_root)

    success, proposal, error = agent.propose_multi_file_change(
        files=[component_path],
        operations=[
            {
                "file": component_path,
                "operation": "rename_prop",
                "selector": "Card",
                "from": "title",
                "to": "heading",
            }
        ],
        intent="Standardize Card prop",
        confidence=0.92,
        source="head_coach",
    )

    assert success is True
    assert error is None
    assert proposal is not None

    auto_review = proposal.auto_review
    assert auto_review is not None
    assert auto_review["status"] == "pass"
    assert auto_review["checks"]["ast_parse"] in {"pass", "skipped"}
    assert auto_review["checks"]["diff_limits"] == "pass"

    manifest = proposal.manifest
    assert manifest is not None
    assert manifest["summary"]["files"] == 1
    assert manifest["changes"][0]["operation"] == "rename_prop"

    # Apply change
    success, result = agent.apply_patch(proposal.proposal_id, "admin")
    assert success is True
    assert isinstance(result, dict)
    assert component_path in result["files"]

    updated = load_file(phase2_project_root, component_path)
    assert 'heading="Hello World"' in updated
    assert 'title=' not in updated


def test_wrap_node_respects_diff_caps(phase2_project_root: Path):
    """
    wrap_node should stay within diff guardrails and capture metadata.
    """
    component_path = "web/src/components/Hero.tsx"
    write_component(
        phase2_project_root,
        component_path,
        """
        export const Hero = () => (
          <HeroSection>
            <h1>Title</h1>
            <p>Subtitle</p>
          </HeroSection>
        );
        """,
    )

    agent = create_agent_for(phase2_project_root)

    success, proposal, error = agent.propose_multi_file_change(
        files=[component_path],
        operations=[
            {
                "file": component_path,
                "operation": "wrap_node",
                "selector": "HeroSection",
                "wrapper": "section",
            }
        ],
        intent="Add semantic section wrapper",
        confidence=0.94,
        source="design_system",
    )

    assert success is True
    assert error is None
    assert proposal is not None

    manifest = proposal.manifest
    assert manifest is not None
    change = manifest["changes"][0]
    assert change["operation"] == "wrap_node"
    assert change["lines_changed"] >= 3

    auto_review = proposal.auto_review
    assert auto_review is not None
    assert auto_review["status"] == "pass"
    assert auto_review["checks"]["diff_limits"] == "pass"


# ============================================================================
# Token Policy Enforcement
# ============================================================================


def test_token_remap_passes_registry(phase2_project_root: Path):
    """
    replace_style_class should validate token mapping via registry.
    """
    component_path = "web/src/components/Button.tsx"
    write_component(
        phase2_project_root,
        component_path,
        """
        export function Button() {
          return <button className="text-gray-600">Click</button>;
        }
        """,
    )

    agent = create_agent_for(phase2_project_root)

    success, proposal, error = agent.propose_multi_file_change(
        files=[component_path],
        operations=[
            {
                "file": component_path,
                "operation": "replace_style_class",
                "from": "text-gray-600",
                "to": "text-foreground-muted",
            }
        ],
        intent="Swap to design token",
        confidence=0.96,
        source="head_coach",
    )

    assert success is True
    assert error is None
    assert proposal is not None

    auto_review = proposal.auto_review
    assert auto_review is not None
    assert auto_review["status"] == "pass"
    assert auto_review["checks"]["token_policy"] == "pass"


def test_token_policy_blocks_custom_hex(phase2_project_root: Path):
    """
    Custom arbitrary styles should fail token policy guardrail.
    """
    component_path = "web/src/components/Badge.tsx"
    write_component(
        phase2_project_root,
        component_path,
        """
        export function Badge() {
          return <span className="text-gray-600">Badge</span>;
        }
        """,
    )

    agent = create_agent_for(phase2_project_root)

    success, proposal, error = agent.propose_multi_file_change(
        files=[component_path],
        operations=[
            {
                "file": component_path,
                "operation": "replace_style_class",
                "from": "text-gray-600",
                "to": "text-[#ff0000]",
            }
        ],
        intent="Attempt custom color",
        confidence=0.9,
        source="head_coach",
    )

    assert success is True  # Proposal still created but auto-review should fail
    assert error is None
    assert proposal is not None

    auto_review = proposal.auto_review
    assert auto_review is not None
    assert auto_review["status"] == "fail"
    assert auto_review["checks"]["token_policy"] == "fail"


# ============================================================================
# Multi-file Bundles + Atomic Rollback
# ============================================================================


def test_multi_file_apply_and_rollback(phase2_project_root: Path):
    """
    Ensure multi-file proposals apply atomically and rollback restores originals.
    """
    first = "web/src/components/Header.tsx"
    second = "web/src/components/SubHeader.tsx"

    write_component(
        phase2_project_root,
        first,
        """
        export function Header() {
          return <Card title="Primary" />;
        }
        """,
    )

    write_component(
        phase2_project_root,
        second,
        """
        export function SubHeader() {
          return <Card title="Secondary" />;
        }
        """,
    )

    agent = create_agent_for(phase2_project_root)

    success, proposal, error = agent.propose_multi_file_change(
        files=[first, second],
        operations=[
            {
                "file": first,
                "operation": "rename_prop",
                "selector": "Card",
                "from": "title",
                "to": "heading",
            },
            {
                "file": second,
                "operation": "rename_prop",
                "selector": "Card",
                "from": "title",
                "to": "heading",
            },
        ],
        intent="Rename Card title prop across bundle",
        confidence=0.93,
        source="migration_bot",
    )

    assert success is True
    assert proposal is not None
    assert proposal.manifest is not None
    assert proposal.manifest["summary"]["files"] == 2

    # Apply atomic bundle
    success, apply_result = agent.apply_patch(proposal.proposal_id, "admin")
    assert success is True
    assert isinstance(apply_result, dict)
    assert len(apply_result["files"]) == 2

    # Files updated
    assert 'heading="Primary"' in load_file(phase2_project_root, first)
    assert 'heading="Secondary"' in load_file(phase2_project_root, second)

    # Rollback restores originals
    success, rollback_result = agent.rollback_proposal(proposal.proposal_id, "admin")
    assert success is True
    assert isinstance(rollback_result, dict)
    assert rollback_result["status"] == "rolled_back"
    assert len(rollback_result["files_restored"]) == 2

    assert 'title="Primary"' in load_file(phase2_project_root, first)
    assert 'title="Secondary"' in load_file(phase2_project_root, second)


# ============================================================================
# Diff Guardrails + Risk Recommendations
# ============================================================================


def test_auto_review_blocks_diff_cap_exceed(phase2_project_root: Path):
    """
    Diff limits should fail when per-file changes exceed 60 lines.
    """
    component_path = "web/src/components/Table.tsx"
    repeated_cards = "\n".join(
        [f'    <Card title="Row {i}" />' for i in range(75)]
    )
    write_component(
        phase2_project_root,
        component_path,
        f"""
        export function Table() {{
          return (
            <div>
        {repeated_cards}
            </div>
          );
        }}
        """,
    )

    agent = create_agent_for(phase2_project_root)

    success, proposal, error = agent.propose_multi_file_change(
        files=[component_path],
        operations=[
            {
                "file": component_path,
                "operation": "rename_prop",
                "selector": "Card",
                "from": "title",
                "to": "heading",
            }
        ],
        intent="Rename Table card props",
        confidence=0.91,
        source="bulk_tool",
    )

    assert success is True
    assert error is None
    assert proposal is not None

    auto_review = proposal.auto_review
    assert auto_review is not None
    assert auto_review["status"] == "fail"
    assert auto_review["checks"]["diff_limits"] == "fail"


def test_high_risk_triggers_manual_review(phase2_project_root: Path):
    """
    Multiple low-impact operations should escalate risk to manual review.
    """
    first = "web/src/components/Tag.tsx"
    second = "web/src/components/Pill.tsx"

    write_component(
        phase2_project_root,
        first,
        """
        export function Tag() {
          return <span className="text-gray-600 bg-gray-100">Tag</span>;
        }
        """,
    )

    write_component(
        phase2_project_root,
        second,
        """
        export function Pill() {
          return <span className="text-gray-600 bg-gray-100">Pill</span>;
        }
        """,
    )

    agent = create_agent_for(phase2_project_root)

    success, proposal, error = agent.propose_multi_file_change(
        files=[first, second],
        operations=[
            {
                "file": first,
                "operation": "replace_style_class",
                "from": "text-gray-600",
                "to": "text-foreground-muted",
            },
            {
                "file": second,
                "operation": "replace_style_class",
                "from": "bg-gray-100",
                "to": "bg-surface-elevated",
            },
        ],
        intent="Swap tokens for Tag/Pill",
        confidence=0.9,
        source="design_system",
    )

    assert success is True
    assert error is None
    assert proposal is not None

    auto_review = proposal.auto_review
    assert auto_review is not None
    assert auto_review["status"] == "pass"
    assert auto_review["recommendation"] == "manual_review"
    assert auto_review["risk_score"] >= 0.3


# ============================================================================
# API Layer — UI Contract
# ============================================================================


def test_api_includes_auto_review_manifest(monkeypatch, phase2_project_root: Path):
    """
    Ensure API responses expose auto_review, manifest, apply + rollback payloads.
    """
    # Seed project with two files and a proposal
    component = "web/src/components/Title.tsx"
    write_component(
        phase2_project_root,
        component,
        """
        export const Title = () => <Heading title="Legacy" />;
        """,
    )

    agent = create_agent_for(phase2_project_root)
    success, proposal, error = agent.propose_multi_file_change(
        files=[component],
        operations=[
            {
                "file": component,
                "operation": "rename_prop",
                "selector": "Heading",
                "from": "title",
                "to": "heading",
            }
        ],
        intent="Rename heading prop",
        confidence=0.95,
        source="ui_bot",
    )
    assert success and proposal is not None and error is None

    # Monkeypatch agent factory used by API endpoints to ensure consistent root
    def _factory(**kwargs: Dict[str, Any]) -> CodexAgent:
        return create_codex_agent(project_root=phase2_project_root)

    monkeypatch.setattr(
        "ReDNACoreDemo.core.jarvis_codex.codex_agent.create_codex_agent",
        _factory,
    )

    from ReDNACoreDemo.core.api import build_app

    client = TestClient(build_app())

    # List proposals
    resp = client.get("/jarvis_codex/proposals")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    listed = payload["proposals"][0]
    assert "auto_review" in listed
    assert "manifest" in listed
    assert listed["auto_review"]["status"] == proposal.auto_review["status"]

    # Apply proposal via API
    resp = client.post(
        "/jarvis_codex/apply",
        json={"proposal_id": proposal.proposal_id, "user": "admin"},
    )
    assert resp.status_code == 200
    apply_payload = resp.json()
    assert apply_payload["ok"] is True
    assert apply_payload["status"] == "applied"
    assert component in apply_payload["files"]

    # Rollback via API
    resp = client.post(
        "/jarvis_codex/rollback",
        json={"proposal_id": proposal.proposal_id, "user": "admin"},
    )
    assert resp.status_code == 200
    rollback_payload = resp.json()
    assert rollback_payload["ok"] is True
    assert rollback_payload["status"] == "rolled_back"
    assert component in rollback_payload["files_restored"]

