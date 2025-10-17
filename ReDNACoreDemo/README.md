# ReDNACoreDemo

**ReDNACoreDemo** is a prototype implementation of the ReDNA **Core**.
It acts as the **source of truth** for a User's ReDNA (digital twin), handling:

- Storage of DNA hierarchies and evidence
- Auditing and provenance tracking
- Event logging and security enforcement
- A hard connector API for integration with engines (UCN/RR) and explorers

Other systems (e.g., coaches, explorers, or external apps) should connect through the **hard connector** rather than accessing internal state directly.

---

## Quick Health Check

Use the smoke test script to quickly verify that Core and UCNRR services are running:

```bash
./scripts/smoke_check.sh
```

This will check the health endpoints:
- Core: `http://127.0.0.1:8015/health`
- UCNRR: `http://127.0.0.1:8011/api/health`

You can customize the ports by setting environment variables:
```bash
CORE_PORT=8015 UCNRR_PORT=8011 ./scripts/smoke_check.sh
```

---

## Project Structure