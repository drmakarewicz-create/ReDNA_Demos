# Human Intelligence Telemetry Endpoint

## Overview

The **human intelligence** endpoint exposes the latest empathy and curiosity telemetry captured by the Head Coach. It is designed for read-only analytics surfaces (DevX Life OS, chat right pane) and returns gracefully even when telemetry does not yet exist.

- **Route:** `GET /ui/hc/life/{user_id}/human_intel`
- **Query params:**
  - `days` *(optional, default 7)* – rolling window for empathy history/trends (`1 ≤ days ≤ 30`)

## Response Shape (summary)

```jsonc
{
  "ok": true,
  "snapshot": {
    "user_id": "USER1",
    "generated_at": "2025-10-12T21:45:39.934Z",
    "window_days": 7,
    "empathy": {
      "latest": {
        "timestamp": "...",
        "emotional_state": "joy",
        "intensity": 0.71,
        "confidence": 0.79,
        "primary_needs": ["celebration"],
        "recommended_actions": ["Celebrate the win"],
        "bonding_metrics": {
          "trust_score": 0.63,
          "rapport_score": 0.58,
          "turns_observed": 9,
          "positive_turns": 5
        }
      },
      "trend": {
        "direction": "up",
        "trust_delta": 0.11,
        "rapport_delta": 0.09,
        "intensity_delta": 0.29
      },
      "samples": 12,
      "history": [... abridged ...]
    },
    "curiosity": {
      "top_gaps": [
        {"target": "CareerDNA.focus_depth", "namespace": "CareerDNA", "debt_score": 0.72},
        {"target": "HealthDNA.sleep_quality", "namespace": "HealthDNA", "debt_score": 0.55}
      ],
      "trend": {
        "direction": "up",
        "average_debt": 0.63,
        "delta": 0.22,
        "stale_targets": 2
      },
      "snapshot": {
        "prompt": "Daily curiosity focus:\n- CareerDNA...",
        "daily_questions": [
          {"target": "CareerDNA.focus_depth", "debt_score": 0.72}
        ],
        "total_records": 14
      }
    }
  },
  "duration_ms": 12.4
}
```

## Data Sources

- **Empathy telemetry:** `data/telemetry/empathy/{user}.jsonl` (written by `EmpathyMonitor.observe_turn`)
- **Curiosity debt:** `data/curiosity/debt/{user}.json` + latest agenda snapshot (optional)

Both readers fail soft – missing files simply return empty structures.

## UI Integrations

| Surface | Usage |
| --- | --- |
| `ReDNACoreDemo/devx/frontend/src/components/LifeInsightsPane.tsx` | Adds a “Human Intelligence” card + modal inside the DevX Life OS pane. |
| `web/src/components/life-os-chat-panel.tsx` | Shows empathy badge, curiosity gaps, and DevX shortcut within the chat sidebar. |

## Smoke Test

Quickly inspect live telemetry with:

```bash
python scripts/smoke_human_intel.py --core http://localhost:8015 --user USER1 --days 7
```

## Notes

- Endpoint avoids mutating debt/telemetry; safe for repeated polling.
- Trend chips report delta in “points” (percentile-style: score × 100).
- If `days` window contains no telemetry, the API returns `samples: 0` with neutral trend (`direction: "steady"`).
