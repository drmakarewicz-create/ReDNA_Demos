# User Assertion Weighting

Self-reports are treated as calibrated evidence, never as absolute truth.  Each assertion starts with a base prior of **0.40** and is clamped to `[0.20, 0.70]` after calibration.

## Calibration

`core/conflict/calibration.CalibrationManager` stores trust scores per user and domain in `data/system/self_report_calibration.json`.  Outcomes update trust:

- `confirmed` → trust +0.05
- `contradicted` → trust −0.05
- `pending` → no change

The resulting trust scales the user assertion base weight: `w_base = 0.20 + trust * (0.70 - 0.20)`.

## Modifiers

`core/conflict/evidence_weighting.compute_effective_weight` adjusts user assertions using provenance metadata:

| Modifier        | Source key      | Range        |
|-----------------|-----------------|--------------|
| Consistency     | `consistency`   | 0.5 – 1.2    |
| Cost/Risk       | `cost_risk`     | 0.7 – 1.3    |
| Time decay      | `time_decay`    | 0.5 – 1.0    |
| Context match   | `context_match` | 0.6 – 1.2    |
| Anonymity       | `anonymity`     | 0.7 (anonymous) / 1.0 (identified) |

Together they produce the effective weight used by the resolver:

```
w_eff = w_base * f_consistency * f_cost_risk * f_time_decay * f_context_match * f_anonymity
```

This keeps user assertions influential but proportional to their historical accuracy and context.

