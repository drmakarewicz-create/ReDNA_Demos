import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ReDNACoreDemo.core.adaptive_analytics.metrics_engine import MetricsEngine
from ReDNACoreDemo.core.adaptive_analytics.insight_aggregator import InsightAggregator


ISO_NOW = datetime(2025, 10, 10, 12, 0, tzinfo=timezone.utc)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def create_user_with_data(root: Path, user_id: str):
    user_dir = root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # Observations with persona and container usage spanning several days
    items = []
    for offset, persona in enumerate(['career', 'relationship', 'career', 'chat', 'career']):
        ts = (ISO_NOW - timedelta(days=offset)).isoformat()
        items.append({
            'user_id': user_id,
            'ts': ts,
            'container': f'SkillDNA.sample_{offset}',
            'persona': persona,
            'weight': 1 + offset * 0.2,
        })
    _write_json(user_dir / 'observations.json', {'items': items})

    # Life OS todos with curiosity metadata
    todos = []
    for offset in range(5):
        ts = (ISO_NOW - timedelta(days=offset)).isoformat()
        todos.append({
            'id': f'todo-{offset}',
            'status': 'done',
            'updated_at': ts,
            'metadata': {
                'curiosity_delta': 0.1 * (offset + 1),
                'focus_weight': 0.2 * (offset + 1),
            },
        })
    _write_jsonl(user_dir / 'hc_life' / 'todos.jsonl', todos)

    goals = [
        {
            'id': 'goal-1',
            'confidence': 0.7,
        },
        {
            'id': 'goal-2',
            'confidence': 0.8,
        },
    ]
    _write_jsonl(user_dir / 'hc_life' / 'goals.jsonl', goals)


def test_metrics_engine_builds_snapshots(tmp_path: Path):
    create_user_with_data(tmp_path, 'alpha')
    engine = MetricsEngine(users_dir=tmp_path)
    snapshots = engine.refresh(force=True)

    assert 'alpha' in snapshots
    snapshot = snapshots['alpha']

    # Persona totals captured from observations
    assert snapshot.persona_totals['career'] > 0
    assert snapshot.persona_totals['relationship'] > 0

    # Container totals and persona mapping preserved
    assert len(snapshot.container_totals) == 5
    container_key = next(iter(snapshot.container_persona_counts))
    assert snapshot.container_persona_counts[container_key]

    # Life OS metrics produce rolling averages and curiosity deltas
    assert snapshot.life_os.tasks_completed_by_day
    assert snapshot.life_os.curiosity_delta_by_day
    assert snapshot.life_os.rolling_7d_average > 0
    assert snapshot.life_os.goal_confidence_avg == 0.75


def test_insight_aggregator_correlations(tmp_path: Path):
    create_user_with_data(tmp_path, 'beta')
    engine = MetricsEngine(users_dir=tmp_path)
    snapshots = engine.refresh(force=True)
    snapshot = snapshots['beta']

    aggregator = InsightAggregator()
    aggregator.ingest(snapshot)

    correlations = aggregator.persona_correlations()
    assert correlations  # Ensure matrix is populated

    related = aggregator.related_personas('career')
    assert isinstance(related, list)

    focus_candidates = aggregator.focus_candidates(limit=3)
    assert len(focus_candidates) <= 3
    assert all(candidate[2] > 0 for candidate in focus_candidates)
