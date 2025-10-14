"""
Integration tests for Ontology V2 API endpoints.

Tests the /api/ontology/* endpoints added in October 2025.
"""

import pytest
from fastapi.testclient import TestClient
from ReDNACoreDemo.core.api import app

client = TestClient(app)


class TestOntologyStatsEndpoint:
    """Tests for GET /api/ontology/stats"""

    def test_stats_endpoint_returns_200(self):
        """Should return 200 OK"""
        response = client.get("/api/ontology/stats")
        assert response.status_code == 200

    def test_stats_has_correct_structure(self):
        """Should return stats with expected structure"""
        response = client.get("/api/ontology/stats")
        data = response.json()

        assert data["ok"] is True
        assert "stats" in data
        stats = data["stats"]

        # Check required fields
        assert "total_containers" in stats
        assert "namespaces" in stats
        assert "status_breakdown" in stats
        assert "sensitive_containers" in stats
        assert "camouflage_containers" in stats
        assert "consent_required" in stats
        assert "metadata" in stats

    def test_stats_total_containers_is_2000(self):
        """Should report 2000 total containers"""
        response = client.get("/api/ontology/stats")
        data = response.json()
        assert data["stats"]["total_containers"] == 2000

    def test_stats_has_14_namespaces(self):
        """Should have 14 namespaces"""
        response = client.get("/api/ontology/stats")
        data = response.json()
        namespaces = data["stats"]["namespaces"]
        assert len(namespaces) == 14

    def test_stats_namespace_counts_sum_to_total(self):
        """Namespace container counts should sum to total"""
        response = client.get("/api/ontology/stats")
        data = response.json()
        stats = data["stats"]

        namespace_sum = sum(stats["namespaces"].values())
        assert namespace_sum == stats["total_containers"]

    def test_stats_sensitive_count_is_valid(self):
        """Sensitive containers count should be reasonable"""
        response = client.get("/api/ontology/stats")
        data = response.json()
        stats = data["stats"]

        # Should be positive and less than total
        assert stats["sensitive_containers"] > 0
        assert stats["sensitive_containers"] <= stats["total_containers"]


class TestOntologyNamespacesEndpoint:
    """Tests for GET /api/ontology/namespaces"""

    def test_namespaces_endpoint_returns_200(self):
        """Should return 200 OK"""
        response = client.get("/api/ontology/namespaces")
        assert response.status_code == 200

    def test_namespaces_has_correct_structure(self):
        """Should return namespaces with expected structure"""
        response = client.get("/api/ontology/namespaces")
        data = response.json()

        assert data["ok"] is True
        assert "namespaces" in data
        assert isinstance(data["namespaces"], dict)

    def test_namespaces_includes_all_expected(self):
        """Should include all 14 expected namespaces"""
        response = client.get("/api/ontology/namespaces")
        data = response.json()
        namespaces = data["namespaces"]

        expected = [
            "BehDNA", "CogDNA", "EmDNA", "EnvDNA",
            "HealthDNA", "HistDNA", "MetaDNA", "PaDNA",
            "PrefDNA", "ProfDNA", "PsyDNA", "RoDNA",
            "SkillDNA", "SocDNA"
        ]

        for ns in expected:
            assert ns in namespaces
            assert namespaces[ns] > 0


class TestOntologyContainersEndpoint:
    """Tests for GET /api/ontology/containers"""

    def test_containers_endpoint_returns_200(self):
        """Should return 200 OK"""
        response = client.get("/api/ontology/containers")
        assert response.status_code == 200

    def test_containers_has_correct_structure(self):
        """Should return containers with expected structure"""
        response = client.get("/api/ontology/containers?limit=10")
        data = response.json()

        assert data["ok"] is True
        assert "containers" in data
        assert "count" in data
        assert "total_available" in data
        assert isinstance(data["containers"], list)

    def test_containers_respects_limit(self):
        """Should respect limit parameter"""
        response = client.get("/api/ontology/containers?limit=5")
        data = response.json()

        assert len(data["containers"]) == 5
        assert data["count"] == 5

    def test_containers_default_limit(self):
        """Should use default limit of 100"""
        response = client.get("/api/ontology/containers")
        data = response.json()

        assert len(data["containers"]) <= 100
        assert data["count"] <= 100

    def test_containers_max_limit_is_1000(self):
        """Should cap limit at 1000"""
        response = client.get("/api/ontology/containers?limit=9999")
        data = response.json()

        assert len(data["containers"]) <= 1000

    def test_containers_namespace_filter(self):
        """Should filter by namespace"""
        response = client.get("/api/ontology/containers?namespace=BehDNA&limit=10")
        data = response.json()

        assert data["ok"] is True
        assert len(data["containers"]) > 0

        # All results should be from BehDNA
        for container in data["containers"]:
            assert container["namespace"] == "BehDNA"

    def test_containers_search_filter(self):
        """Should search by query string"""
        response = client.get("/api/ontology/containers?search=routine&limit=10")
        data = response.json()

        assert data["ok"] is True
        assert len(data["containers"]) > 0

        # Results should contain "routine" somewhere
        for container in data["containers"]:
            text = (
                container["path"].lower() +
                container["description"].lower() +
                " ".join(container["tags"]).lower()
            )
            assert "routine" in text

    def test_containers_combined_filters(self):
        """Should support namespace + search together"""
        response = client.get(
            "/api/ontology/containers?namespace=BehDNA&search=habit&limit=10"
        )
        data = response.json()

        assert data["ok"] is True
        if len(data["containers"]) > 0:
            for container in data["containers"]:
                assert container["namespace"] == "BehDNA"

    def test_container_has_required_fields(self):
        """Container objects should have all required fields"""
        response = client.get("/api/ontology/containers?limit=1")
        data = response.json()

        assert len(data["containers"]) > 0
        container = data["containers"][0]

        required_fields = [
            "id", "namespace", "path", "version", "status",
            "description", "tags", "sensitive", "camouflage",
            "consent_required", "parent_containers",
            "created_at", "updated_at"
        ]

        for field in required_fields:
            assert field in container


class TestOntologyContainerByIdEndpoint:
    """Tests for GET /api/ontology/container/{id}"""

    def test_container_by_id_returns_200(self):
        """Should return 200 for valid container ID"""
        response = client.get("/api/ontology/container/BehDNA.v1")
        assert response.status_code == 200

    def test_container_by_id_has_correct_structure(self):
        """Should return container with expected structure"""
        response = client.get("/api/ontology/container/BehDNA.v1")
        data = response.json()

        assert data["ok"] is True
        assert "container" in data
        assert data["container"]["id"] == "BehDNA.v1"

    def test_container_by_id_not_found(self):
        """Should return 404 for invalid container ID"""
        response = client.get("/api/ontology/container/InvalidContainer.v999")
        assert response.status_code == 404

    def test_container_by_id_returns_full_details(self):
        """Should return complete container information"""
        response = client.get("/api/ontology/container/BehDNA.v1")
        data = response.json()
        container = data["container"]

        # Check for detailed fields
        assert "discovery" in container
        assert "validation_rules" in container
        assert "changelog" in container
        assert "ucn_weight_hint" in container
        assert "ai_upgradable" in container

    def test_multiple_container_lookups(self):
        """Should handle multiple sequential lookups"""
        ids = ["BehDNA.v1", "CogDNA.v1", "PaDNA.v1"]

        for container_id in ids:
            response = client.get(f"/api/ontology/container/{container_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["container"]["id"] == container_id


class TestOntologyAPIPerformance:
    """Performance tests for ontology endpoints"""

    def test_stats_endpoint_is_fast(self):
        """Stats endpoint should respond quickly"""
        import time

        start = time.time()
        response = client.get("/api/ontology/stats")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0  # Should be under 1 second

    def test_search_endpoint_is_fast(self):
        """Search endpoint should respond quickly"""
        import time

        start = time.time()
        response = client.get("/api/ontology/containers?search=behavior&limit=50")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0  # Should be under 1 second


class TestOntologyAPIEdgeCases:
    """Edge case tests for ontology endpoints"""

    def test_empty_search_query(self):
        """Should handle empty search query"""
        response = client.get("/api/ontology/containers?search=")
        assert response.status_code == 200

    def test_search_no_results(self):
        """Should handle search with no results gracefully"""
        response = client.get("/api/ontology/containers?search=xyznonexistent123")
        data = response.json()

        assert data["ok"] is True
        assert data["count"] == 0
        assert len(data["containers"]) == 0

    def test_invalid_namespace_filter(self):
        """Should handle invalid namespace gracefully"""
        response = client.get("/api/ontology/containers?namespace=InvalidDNA")
        data = response.json()

        assert response.status_code == 200
        assert data["count"] == 0

    def test_zero_limit(self):
        """Should handle limit=0"""
        response = client.get("/api/ontology/containers?limit=0")
        data = response.json()

        assert response.status_code == 200
        # Should return at least 1 or use default

    def test_negative_limit(self):
        """Should handle negative limit"""
        response = client.get("/api/ontology/containers?limit=-5")
        data = response.json()

        assert response.status_code == 200
        # Should use default or minimum

    def test_special_characters_in_search(self):
        """Should handle special characters in search"""
        response = client.get("/api/ontology/containers?search=test%20%2B%20special")
        assert response.status_code == 200


class TestOntologyDataQuality:
    """Tests for ontology data quality"""

    def test_all_containers_have_namespace(self):
        """All containers should have a valid namespace"""
        response = client.get("/api/ontology/containers?limit=100")
        data = response.json()

        for container in data["containers"]:
            assert container["namespace"]
            assert len(container["namespace"]) > 0

    def test_all_containers_have_descriptions(self):
        """All containers should have descriptions"""
        response = client.get("/api/ontology/containers?limit=100")
        data = response.json()

        for container in data["containers"]:
            assert container["description"]
            assert len(container["description"]) > 0

    def test_container_ids_are_unique(self):
        """Container IDs should be unique"""
        response = client.get("/api/ontology/containers?limit=1000")
        data = response.json()

        ids = [c["id"] for c in data["containers"]]
        assert len(ids) == len(set(ids))  # No duplicates

    def test_container_versions_are_positive(self):
        """Container versions should be positive integers"""
        response = client.get("/api/ontology/containers?limit=100")
        data = response.json()

        for container in data["containers"]:
            assert container["version"] > 0
            assert isinstance(container["version"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
