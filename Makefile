.PHONY: up down logs manifest manifest-open manifest-ports manifest-check health consent-secret consent-health

COMPOSE ?= docker compose
PYTHON ?= python3
MANIFEST = docs/ReDNA_Workspace_Manifest.md
HEALTH_USER ?= ai_ready_probe

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

manifest:
	@echo "📄 Manifest lives at $(MANIFEST)"

manifest-open:
	@$(PYTHON) -m ReDNACoreDemo.devx.manifest_parser open "$(MANIFEST)"

manifest-check:
	@$(PYTHON) -m ReDNACoreDemo.devx.manifest_parser check "$(MANIFEST)"

manifest-ports:
	@$(PYTHON) -m ReDNACoreDemo.devx.manifest_parser ports "$(MANIFEST)"

health:
	@echo "RR audit:" && (curl -s http://127.0.0.1:8004/core/debug/rr_audit/$(HEALTH_USER) | jq '.summary // .' || true)
	@echo
	@echo "UCN propagation:" && (curl -s http://127.0.0.1:8004/core/debug/ucn_propagation/$(HEALTH_USER) | jq '.summary // .' || true)
	@echo
	@echo "Ontology:" && (curl -s http://127.0.0.1:8004/core/graph/ontology | jq 'def count_items($v): if ($v|type) == "array" or ($v|type) == "object" then ($v|length) elif ($v|type) == "number" then $v else 0 end; {nodes: count_items(.nodes // []), edges: count_items(.edges // [])}' || true)

consent-secret:
	@printf 'CONSENT_JWT_SECRET=%s\n' "$$(openssl rand -hex 32)" >> .env
	@echo 'CONSENT_JWT_TTL_MINUTES=15' >> .env
	@echo "✅ Wrote new consent secret to .env"
	@echo "⚠️  Restart Core API via CP++ Nuclear to apply changes"

consent-health:
	@curl -s http://127.0.0.1:8004/core/consent/health | jq .
