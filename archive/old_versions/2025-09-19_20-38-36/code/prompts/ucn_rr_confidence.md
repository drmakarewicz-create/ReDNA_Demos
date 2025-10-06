# UCN Calibration Guide

Use these reference points when assigning UCN (User Confidence Number):

- 60 — weak inference (implicit, one cue, plausible but unconfirmed)
- 80 — moderate explicit (clear direct statement, typical reliability)
- 100 — strong explicit (clear statement + secondary cue)
- 120 — very strong (explicit + corroboration / repeated evidence)
- 150+ — near-certain (multiple corroborations from separate inputs)
- Do not emit traits at all if confidence would be < 60.
- Add short "reasons" strings that justify the UCN.