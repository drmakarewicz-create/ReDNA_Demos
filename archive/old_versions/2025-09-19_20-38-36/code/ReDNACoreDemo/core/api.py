# ReDNACoreDemo/core/api.py
from __future__ import annotations
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import hierarchy
from .storage import ensure_dirs_for_user, read_user_state, write_user_state
from .schemas import BundleIn
from .redna_core import build_observations, resolve_traits
from .events import capture
from .security import allow

def build_app() -> FastAPI:
    app = FastAPI(title="ReDNA Core Demo", version="2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True, "traits_known": len(hierarchy.all_trait_keys())}

    @app.post("/user/{user_id}/ensure")
    def ensure_user(user_id: str):
        ensure_dirs_for_user(user_id)
        resolved, evidence, obs = read_user_state(user_id)
        return {"ok": True, "resolved_keys": len(resolved)}

    @app.get("/user/{user_id}/resolved")
    def get_resolved(user_id: str):
        resolved, evidence, obs = read_user_state(user_id)
        return {"user_id": user_id, "resolved": resolved}

    @app.get("/catalog")
    def catalog():
        # Wide table support in Explorer (“show all traits even if empty”)
        return {"registry": hierarchy.REGISTRY, "all_keys": hierarchy.all_trait_keys()}

    @app.post("/ingest_bundle")
    def ingest_bundle(payload: BundleIn):
        user_id = payload.get("user_id", "").strip()
        if not user_id:
            raise HTTPException(400, "missing user_id")
        if not allow(user_id):
            raise HTTPException(403, "forbidden")

        ensure_dirs_for_user(user_id)
        prior_resolved, prior_evidence, prior_obs = read_user_state(user_id)

        new_obs = build_observations(payload.get("items", []))
        (out, evidence, observations) = resolve_traits(
            prior_resolved, prior_evidence, prior_obs, new_obs
        )

        write_user_state(user_id, out["resolved"], evidence, observations)
        capture(user_id, "bundle_ingested", {"count": len(payload.get("items", []))})
        return {"ok": True, "resolved_count": len(out["resolved"]), "priorities": out["priorities"]}

    @app.post("/recompute/{user_id}")
    def recompute(user_id: str):
        # no-op pass through since we recompute on every ingest; still useful
        resolved, evidence, obs = read_user_state(user_id)
        write_user_state(user_id, resolved, evidence, obs)
        return {"ok": True, "resolved_count": len(resolved)}

    return app