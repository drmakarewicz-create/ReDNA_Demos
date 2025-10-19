import importlib
from pathlib import Path


def test_learning_snapshot_initializes(tmp_path, monkeypatch):
    learning_module = importlib.import_module('ReDNACoreDemo.core.conflict.learning')
    importlib.reload(learning_module)
    cache_path = tmp_path / 'conflict_learning_snapshot.json'
    monkeypatch.setattr(learning_module, 'LEARNING_CACHE', cache_path, raising=False)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = learning_module.get_learning_snapshot()
    assert snapshot['generated_at'] is not None
    assert 'weights' in snapshot
    assert cache_path.exists()
