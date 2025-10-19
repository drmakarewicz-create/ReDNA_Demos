import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ReDNACoreDemo.core.adaptive_analytics import AdaptiveAnalyticsService, MetricsEngine
from ReDNACoreDemo.devx.backend import adaptive_analytics_api

ISO_NOW = datetime(2025, 10, 10, 15, 0, tzinfo=timezone.utc)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def seed_user(tmp_path: Path, user_id: str, persona: str):
    user_dir = tmp_path / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    items = []
    for offset in range(4):
        ts = (ISO_NOW - timedelta(days=offset)).isoformat()
        items.append({
            'user_id': user_id,
            'ts': ts,
            'container': f'SkillDNA.focus_{offset}',
            'persona': persona,
            'weight': 1 + offset * 0.3,
        })
    _write_json(user_dir / 'observations.json', {'items': items})

    todos = []
    for offset in range(4):
        ts = (ISO_NOW - timedelta(days=offset)).isoformat()
        todos.append({
            'id': f'{user_id}-todo-{offset}',
            'status': 'done',
            'updated_at': ts,
            'metadata': {'curiosity_delta': 0.05 * (offset + 1)},
        })
    _write_jsonl(user_dir / 'hc_life' / 'todos.jsonl', todos)

    goals = [
        {'id': f'{user_id}-goal', 'confidence': 0.65},
    ]
    _write_jsonl(user_dir / 'hc_life' / 'goals.jsonl', goals)


def build_service(tmp_path: Path) -> AdaptiveAnalyticsService:
    engine = MetricsEngine(users_dir=tmp_path)
    service = AdaptiveAnalyticsService(metrics_engine=engine)
    service.refresh(force=True)
    return service


def test_predictor_latency(tmp_path: Path):
    seed_user(tmp_path, 'gamma', 'career')
    service = build_service(tmp_path)

    start = time.perf_counter()
    predictions = service.predictor.predict_next_focus('gamma', limit=3)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert predictions
    assert elapsed_ms < 200


def test_adaptive_analytics_endpoints(tmp_path: Path, monkeypatch):
    seed_user(tmp_path, 'delta', 'career')
    seed_user(tmp_path, 'epsilon', 'relationship')

    service = build_service(tmp_path)

    # Patch global service used by API router
    monkeypatch.setattr(adaptive_analytics_api, 'adaptive_service', service)

    app = FastAPI()
    app.include_router(adaptive_analytics_api.router)

    client = TestClient(app)

    overview_resp = client.get('/devx/api/adaptive-analytics/overview')
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert 'users' in overview and len(overview['users']) == 2

    user_resp = client.get('/devx/api/adaptive-analytics/user/delta')
    assert user_resp.status_code == 200
    payload = user_resp.json()
    assert payload['user_id'] == 'delta'
    assert payload['predictions']
    assert payload['latency_ms'] >= 0
    assert payload['learning_velocity']['rolling_avg_7d'] > 0
