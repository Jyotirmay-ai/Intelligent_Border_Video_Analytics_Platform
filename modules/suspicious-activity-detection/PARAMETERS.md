# IBVAP — Suspicious Activity Detection Parameters

**Related docs:** `ARCHITECTURE.md` §3 (rules engine), `PHASES.md` Phase 5,
`RULES.md` §5 (Boundaries of AI), `PRD.md` §4.6

This document is the single source of truth for the parameters that drive suspicious-
activity detection. It is designed to be **config, not code** — every parameter here
lives in a per-zone record in the database (see §9), editable by an authorized operator
through the same geofence editor UI, not hardcoded into the rules engine.

---

## 0. Philosophy

- **Composite rules, not single triggers.** No individual parameter below should fire a
  high/critical alert by itself. Real signal comes from combinations (see §8).
- **Per-zone, not global.** "Suspicious loiter time" near a farming footpath and near an
  official crossing are different numbers. Every threshold is scoped to a zone.
- **Field-tuned, not assumed.** Every default value in this document is a **starting
  point** for Phase 5/7 pilot tuning against real footage — not a validated number.
- **Posture caution.** Posture-based cues (crouching, crawling) have the highest false-
  positive rate of anything in this system — people crouch to rest, tie shoes, or farm.
  They contribute to severity; they never stand alone as a critical trigger.

---

## 1. Spatial / Proximity Parameters

| Parameter | Description | Starting default |
|---|---|---|
| `proximity_bands_m` | Concentric distance bands from the fence line, each with its own severity | Outer watch: 200m · Warning: 50m · Restricted: 15m |
| `approach_vector` | Toward / paralleling / away from the boundary | Paralleling at close range for extended time is the highest-interest case |
| `boundary_probe_count` | Number of approach-then-retreat cycles by the same track in one session | ≥2 probes flags as reconnaissance-pattern candidate |

## 2. Temporal Parameters

| Parameter | Description | Starting default |
|---|---|---|
| `dwell_time_threshold_s` | Time stationary/near-stationary within a zone before "loitering" fires | 90–120s in restricted zone |
| `night_multiplier` | Multiplier applied to thresholds during night hours (lower = more sensitive) | 0.6× dwell time, 0.5× group-size baseline |
| `recurrence_window_days` | Same approach path/time-of-day repeating across days — a pattern-of-life signal that needs event history, not just live frame analysis | Flag on 3rd occurrence within 7 days |

## 3. Motion / Kinematic Parameters

| Parameter | Description | Starting default |
|---|---|---|
| `speed_thresholds_mps` | Both unusually slow (surveillance/route-finding) and unusually fast (evasion) are more interesting than "normal" | Slow: <0.3 m/s sustained · Fast: >3.5 m/s crossing a zone |
| `path_linearity` | Erratic/doubling-back paths score differently than a direct walk along a known trail | Flag if path deviates >40% from straight-line distance |
| `camera_aware_reversal` | Direction change coinciding with entering a camera's field of view, repeated across sightings | Flag on 2nd occurrence for the same track |

## 4. Group Parameters

| Parameter | Description | Starting default |
|---|---|---|
| `group_size_baseline` | Typical group size for this zone/time-of-day | Set per zone from historical data |
| `group_size_alert` | Threshold above baseline that raises severity | Baseline + 1, tighter at night |
| `formation_spacing` (v2) | Tight tactical spacing / staggered line vs. loose cluster | Deferred — add after v1 group-size thresholds are validated |

## 5. Posture Parameters (via pose keypoints)

| Parameter | Description | Starting default |
|---|---|---|
| `posture_flags` | Crouch, crawl, climb, prone | Sustained >5s to filter out momentary poses (tying a shoe, bending) |
| `carried_object_codetection` | Object detected with a person near the boundary | Flag the **combination**, never the object alone — tool-shaped items are common with legitimate agricultural activity near border land |

> **Hard rule:** no `posture_flags` value alone triggers "high" or "critical" severity.
> It must combine with a proximity or temporal parameter (see §8).

## 6. Vehicle Parameters

| Parameter | Description | Starting default |
|---|---|---|
| `vehicle_idle_threshold_s` | Stopped/idling duration near the fence | 180s |
| `repeat_pass_window_min` | Same vehicle passing the same stretch multiple times in a window | 2+ passes in 30 min |
| `occupancy_anomaly` | Rough headcount exceeding what the vehicle type/registration would suggest, where camera angle allows | Configurable per vehicle class |
| `unregistered_plate_geofence_entry` | Already covered by the ANPR pipeline (`PRD.md` FR-15) | — |

## 7. Multi-Camera Correlation Parameters

| Parameter | Description | Starting default |
|---|---|---|
| `cross_camera_reappearance_window_min` | Same re-identified track appearing at non-adjacent cameras within a time window — suggests scouting a stretch, not passing through one point | 45 min, tuned per BOP sector size |

This is the one category that specifically needs BoT-SORT+ReID rather than plain
ByteTrack (see `ARCHITECTURE.md` §3) — plain ByteTrack does not carry identity across
non-overlapping camera views.

---

## 8. Composite Rules

Composite rules are what actually keep the false-positive rate manageable. Each rule
combines 2+ parameters and maps to a severity.

| Rule name | Conditions (AND) | Severity |
|---|---|---|
| `reconnaissance-pattern` | dwell_time > threshold, zone = restricted, time = night | High |
| `coordinated-group-movement` | group_size ≥ group_size_alert, approach_vector = toward, time = off-hours | High |
| `possible-breach-attempt` | posture = climb, zone = restricted | Critical |
| `sector-scouting` | cross_camera_reappearance within window, ≥2 distinct cameras | High |
| `vehicle-surveillance` | vehicle_idle > threshold, repeat_pass ≥ 2 | Medium |
| `casual-proximity` (no alert) | present in outer-watch zone, dwell < 30s, daytime | None |

New composite rules are added as **data**, not code — see §9 schema.

---

## 9. Configuration Schema

Stored per zone (extends the geofence record in PostGIS — see `ARCHITECTURE.md` §3):

```json
{
  "zone_id": "zone-b-restricted",
  "proximity_bands_m": [200, 50, 15],
  "dwell_time_threshold_s": 120,
  "night_multiplier": 0.6,
  "group_size_baseline": 2,
  "group_size_alert": 3,
  "speed_thresholds_mps": { "slow": 0.3, "fast": 3.5 },
  "posture_flags": ["crouch", "crawl", "climb", "prone"],
  "vehicle_idle_threshold_s": 180,
  "vehicle_repeat_pass_window_min": 30,
  "cross_camera_reappearance_window_min": 45,
  "composite_rules": [
    {
      "rule_id": "reconnaissance-pattern",
      "conditions": ["dwell_time > dwell_time_threshold_s", "zone == restricted", "time == night"],
      "severity": "high"
    }
  ],
  "created_by": "op_id",
  "approved_by": "supervisor_id",
  "version": 3,
  "updated_at": "2026-08-29T10:00:00Z"
}
```

This schema travels through the same hot-reload pub/sub path as geofence updates
(`ARCHITECTURE.md` §3, `PRD.md` FR-19) — an operator edits thresholds in the dashboard,
the edge rules engine picks them up within the same time budget, no redeploy.

---

## 10. Field-Tuning Process

1. Deploy with the starting defaults above, logged but not yet used to page anyone
   (shadow mode).
2. Collect a pilot window (Phase 5/7) of flagged vs. operator-dispositioned events.
3. Adjust per-zone thresholds based on actual false-positive/false-negative rates —
   thresholds will differ meaningfully between a forest stretch, a farming trail, and an
   official crossing.
4. Re-run shadow mode after any threshold change before it goes live for real alerting.
5. Record every threshold change with who approved it — this is a security-relevant
   config change like any geofence edit (`RULES.md` §6 audit trail).
