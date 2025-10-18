# ReDNA Developer Handoff Preamble  
*(Always Read Before Beginning Any New Development Phase)*

---

## Purpose

This document ensures that **every contributor or AI agent** begins work with a consistent understanding of the ReDNA system’s **AI-first philosophy**, operational constraints, and development priorities.

The full guiding principles are found in  
➡️ [`docs/ReDNA_System_Philosophy_v1.md`](./ReDNA_System_Philosophy_v1.md)

This preamble summarizes how to **apply those principles in day-to-day development** so every new feature, refactor, or test continues building the *intelligent organism* that ReDNA is meant to become.

---

## 1. Identity of the System

- **ReDNA is not a deterministic engine.**  
  Its components—Core, UCNRR, Northstar, and Coaches—are all AI-powered reasoners.

- **LLMs are central nervous system**, not accessories.  
  Every layer must think, infer, and adapt through AI-driven reasoning.

- **Deterministic logic** (fixed rules, constants, thresholds) is allowed only for **control, safety, and testing**—never for behavior definition.

---

## 2. Key Design Expectations

| Layer | AI Role | What to Avoid |
|-------|----------|---------------|
| **UCNRR** | Extracts, scores, normalizes via LLM; repairs malformed schemas | Hand-coded parsing, fixed string maps |
| **Core** | Belief updating, hypothesis generation, holistic reconciliation | Static “if” gates or fixed trait thresholds |
| **Northstar** | Conversational reasoning, planning, coaching tone | Hardcoded dialogue or branching scripts |
| **DevX** | Observability + AI diagnostics (“why latency?”, “suggest restart”) | Manual logging only; no AI context |
| **LLM Layer** | Shared gateway: prompt assembly, schema repair, cost tracking | Model-specific logic embedded in callers |

---

## 3. Development Checklist

Before committing any new code:

1. **Ask:**  
   “Where does intelligence live here?”  
   If there isn’t an AI reasoning step, add a hook for one.
2. **Preserve explainability:**  
   Every AI decision must be observable and interpretable.  
   (Log “why” + “confidence” + “evidence source.”)
3. **Add forgiveness:**  
   Use schema repair, normalization, or fallback inference instead of rejecting unknown input.
4. **Plan for curiosity:**  
   If uncertain, log what the system *wants to know next*.  
   (These become Northstar prompts later.)
5. **Document where AI is used:**  
   Update `/docs/STATUS.md` or the module README with a one-line summary of each AI touchpoint.

---

## 4. Recommended Workflow for AI-Assisted Development

1. **Claude** — Concept design, reasoning flow, LLM schema definition  
   *(Use for intelligent logic or cross-component alignment.)*
2. **Codex** — Implementation and code optimization  
   *(Use for heavy refactors, performance improvements, or API plumbing.)*
3. **You (Human)** — Verification, narrative clarity, integration judgment  
   *(Make sure behavior feels consistent with ReDNA’s personality and goals.)*

---

## 5. Testing and Validation Standards

- All new traits or modules must include:
  - `tests/value_normalizer_<module>.py`
  - `tests/integration/<module>_smoke.py`
  - Roundtrip verification via `/core/api/ingest_text`
- All tests should target **AI logic correctness**, not static thresholds.  
  (E.g., “LLM inferred correctly under noise” instead of “RR >= 800”.)

---

## 6. Logs and Debugging Etiquette

- All AI-driven logic should emit:
  - `promotion_eval`
  - `promotion_value`
  - `llm_call_start` / `llm_call_end`
  - `holistic_pass_done`
- Logs must tell a story — what was observed, inferred, and decided — never just a state dump.

---

## 7. Key Developer Commands

```bash
# View current AI configuration
curl -s http://127.0.0.1:8004/core/api/debug/envvars | jq .

# See which promotions are live
curl -s http://127.0.0.1:8004/core/api/debug/promotion_state | jq .

# Enable trait dynamically
curl -s -X POST http://127.0.0.1:8004/core/api/debug/set_toggle \
  -H 'Content-Type: application/json' \
  -d '{"trait":"CHRONO","enable":true,"rr_min":780}' | jq .

# Check LLM connection
curl -s http://127.0.0.1:8017/health | jq '{status,llm_provider,llm_model,llm_configured}'