---

# 2) Drop-in: `prompts/core_ai_propagation.md`  (normalize + propagate)
Paste at `ReDNA_Demos/prompts/core_ai_propagation.md`:

```markdown
# Core — Arbitration & Propagation

Role: Take incoming observations from UCN/RR and produce a **resolved** map aligned to the official ReDNA hierarchy. Then **propagate** reasonable linked traits with calibrated UCN. Merge with existing truths without clobbering higher-confidence values.

## Input (context to the model)
- CURRENT_RESOLVED: existing resolved map (may be large; treat as authoritative unless new info has higher UCN)
- NEW_OBSERVATIONS: new traits (dot-paths) from UCN/RR

## Output (STRICT JSON)
```json
{
  "resolved": {
    "<Trait.Path>": { "resolved_value": <value>, "ucn": <0–200>, "reasons": [ "why" ] }
  }
}