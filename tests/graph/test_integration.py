from __future__ import annotations

import json
from importlib import reload

class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code == 200
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


def test_chronotype_promotion_populates_belief_graph(tmp_path, monkeypatch):
    data_root = tmp_path / "core_data"
    monkeypatch.setenv("REDNA_CORE_DATA", str(data_root))
    monkeypatch.setenv("CORE_DATA_ROOT", str(data_root))
    monkeypatch.setenv("PROMOTE_ENABLE_CHRONO", "true")
    monkeypatch.setenv("REDNA_HOME", str(tmp_path / ".redna"))

    import ReDNACoreDemo.core.storage as storage_module
    reload(storage_module)
    import ReDNACoreDemo.core.graph.storage as graph_storage_module
    reload(graph_storage_module)
    import ReDNACoreDemo.core.api as core_api
    reload(core_api)
    from fastapi.testclient import TestClient

    fake_payload = {
        "ok": True,
        "rr_by_trait": {"BehaviorDNA.Sleep.Chronotype": 820.0},
        "curiosity_by_trait": {"BehaviorDNA.Sleep.Chronotype": 0.18},
        "why_by_trait": {"BehaviorDNA.Sleep.Chronotype": "Chronotype signal detected (morning lark)."},
        "ucn_by_trait": {"BehaviorDNA.Sleep.Chronotype": {"u": 0.2, "c": 0.7, "n": 0.1}},
    }

    monkeypatch.setattr(core_api.requests, "post", lambda *args, **kwargs: FakeResponse(fake_payload))

    user_id = "graph_integration_user"
    text = "I'm a total morning person—up at 5AM and energized before sunrise."

    client = TestClient(core_api.app, raise_server_exceptions=False)
    response = client.post("/ui/ingest/text", json={"user_id": user_id, "text": text, "source": "unit_test"})
    assert response.status_code == 200, response.json()
    result = response.json()
    assert isinstance(result, dict)
    assert result.get("ok") is True

    graph_storage = core_api.get_graph_storage()
    graph = graph_storage.load_user_graph(user_id)

    trait_nodes = [
        node for node in graph.nodes if node.node_type == "trait_belief" and node.trait_id == "BehaviorDNA.Sleep.Chronotype"
    ]
    obs_nodes = [node for node in graph.nodes if node.node_type == "observation"]
    evidence_edges = [edge for edge in graph.edges if edge.edge_type == "evidence_for"]

    assert trait_nodes, "expected Chronotype trait node"
    assert obs_nodes, "expected observation node"
    assert len(evidence_edges) == 1

    evidence_edge = evidence_edges[0]
    observation_node = next(node for node in obs_nodes if node.node_id == evidence_edge.from_node)
    trait_node = next(node for node in trait_nodes if node.node_id == evidence_edge.to_node)

    assert evidence_edge.from_node == observation_node.node_id
    assert evidence_edge.to_node == trait_node.node_id
    assert evidence_edge.edge_type == "evidence_for"
