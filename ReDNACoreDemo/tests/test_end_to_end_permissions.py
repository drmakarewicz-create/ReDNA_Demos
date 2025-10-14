import asyncio
import importlib

import httpx
import pytest


@pytest.mark.asyncio
async def test_permission_flow_denied_grant_allow_revoke(tmp_path, monkeypatch):
    """
    Minimal end-to-end test covering capability enforcement:
    deny → grant → allow → revoke → deny.
    """
    # Ensure consent storage writes into tmp path to avoid polluting real data
    monkeypatch.setenv("CONSENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CONSENT_JWT_SECRET", "TEST_SECRET")
    monkeypatch.setenv("CONSENT_JWT_LEEWAY_SECONDS", "20000")

    # Reload consent storage/app to honor temporary directory
    consent_storage = importlib.reload(importlib.import_module("ReDNACoreDemo.services.consent.storage"))
    importlib.reload(importlib.import_module("ReDNACoreDemo.services.consent.jwt_utils"))
    consent_api = importlib.reload(importlib.import_module("ReDNACoreDemo.services.consent.api"))
    consent_app = consent_api.app

    # Rebuild policy engine dependencies after storage reload
    importlib.reload(importlib.import_module("ReDNACoreDemo.core.policy.policy_engine"))
    importlib.reload(importlib.import_module("ReDNACoreDemo.core.use_api.middleware"))
    core_api_module = importlib.reload(importlib.import_module("ReDNACoreDemo.core.api"))
    core_app = core_api_module.build_app()

    consent_transport = httpx.ASGITransport(app=consent_app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=consent_transport, base_url="http://consent.test") as consent_client:
        # Grant capability via consent service
        grant_payload = {
            "user_id": "TEST",
            "grantee_id": "career_coach",
            "purpose": "resume_builder",
            "scopes": ["read:SkillDNA"],
            "suggested_ttl": "PT1H",
            "reuse_limit": None,
            "export_allowed": False,
            "aggregate_only": False,
        }
        grant_response = await consent_client.post("/consent/grant", json=grant_payload)
        assert grant_response.status_code == 200, grant_response.text
        grant_body = grant_response.json()
        cap_id = grant_body["cap_id"]
        jwt_token = grant_body["jwt"]

        # Adjust iat slightly backward to avoid strict clock skew in tests
        # Token is minted with UTC timestamps; leeway env ensures compatibility during tests

        core_transport = httpx.ASGITransport(app=core_app, raise_app_exceptions=False)

        async with httpx.AsyncClient(transport=core_transport, base_url="http://core.test") as core_client:
            # Without JWT → expect failure (middleware enforces capability)
            unauthorized = await core_client.get("/core/use/SkillDNA/read", params={"user_id": "TEST"})
            assert unauthorized.status_code >= 400

            # With JWT → expect 200
            authorized = await core_client.get(
                "/core/use/SkillDNA/read",
                params={"user_id": "TEST"},
                headers={"Authorization": f"Bearer {jwt_token}"},
            )
            assert authorized.status_code == 200
            body = authorized.json()
            assert body["scope"] == "SkillDNA"

        # Revoke capability
        revoke_response = await consent_client.post(
            "/consent/revoke", json={"cap_id": cap_id, "reason": "test cleanup"}
        )
        assert revoke_response.status_code == 200

        async with httpx.AsyncClient(transport=core_transport, base_url="http://core.test") as core_client:
            revoked = await core_client.get(
                "/core/use/SkillDNA/read",
                params={"user_id": "TEST"},
                headers={"Authorization": f"Bearer {jwt_token}"},
            )
            assert revoked.status_code >= 400
