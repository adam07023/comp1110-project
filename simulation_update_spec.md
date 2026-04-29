# Restaurant Queue Simulation — Extension Spec

## Overview

This document specifies the changes required to extend the restaurant queue simulation from a single-stage (arrive → seat → depart) model to a multi-stage pipeline (arrive → order → seat → depart), alongside supporting additions: a reservation system, extended seating strategies, updated abandonment modelling, and updated business model presets.

---

## 1. Architecture Change: Multi-Stage Pipeline

### Current architecture
Groups arrive → join seating queue → get seated → depart.

### New architecture
Groups arrive → join ordering queue → complete ordering → join seating queue → get seated → depart.

Patience is measured from arrival time and applies across both stages. A group can abandon at any point before being seated.

---

## 2. New Parameters

### 2.1 Ordering Parameters (added to `BusinessModel`)

```python
servers: int
# Number of counter staff available concurrently.

ordering_type: str  # "counter_only" | "hybrid"
# Determines whether kiosks are available.

counter_order_time_min: int
counter_order_time_max: int
counter_order_time_mean: float
counter_order_time_sd: float
# Truncated normal distribution for counter ordering duration.
# Bounds: [counter_order_time_min, counter_order_time_max]

kiosks: int
# Number of self-service kiosk terminals. 0 if ordering_type is counter_only.

kiosk_usage_percent: float
# Probability [0.0, 1.0] that a group uses a kiosk when ordering_type is hybrid.
# Ignored if ordering_type is counter_only.

kiosk_order_time_min: int
kiosk_order_time_max: int
kiosk_order_time_mean: float
kiosk_order_time_sd: float
# Truncated normal distribution for kiosk ordering duration.
# Only used when ordering_type is hybrid.
```

### 2.2 Reservation Parameters (added to `BusinessModel`)

```python
reservation_policy: str  # "none" | "hybrid_allocation"
# "none": all tables available to walk-ins.
# "hybrid_allocation": a proportion of tables are reserved for pre-booked groups.

reserved_table_percent: float
# Proportion of tables allocated for reservations. Only used when
# reservation_policy is "hybrid_allocation". Example: 0.5 means half of
# all tables are reserved.

reservation_hold_before_min: int
# Minutes before a reservation's scheduled arrival that the table is
# removed from walk-in availability. Example: 15 means the table is
# held starting 15 minutes before the booking time.

reservation_hold_after_min: int
# Minutes after a reservation's scheduled arrival that the table waits
# before being released back to walk-ins if the party has not shown up.
# Example: 15 means a no-show table is released 15 minutes after the
# scheduled time.
```

### 2.3 Updated `GeneratorProfile`

```python
dining_duration_mean: float
dining_duration_sd: float
# Parameters for truncated normal sampling of dining duration.
# Bounds remain min_dining_duration and max_dining_duration.
# Food truck uses uniform sampling and ignores these fields.
```

---

## 3. Sampling Distributions

| Parameter | Distribution | Notes |
|---|---|---|
| Dining duration | Truncated normal | All models except food truck |
| Dining duration (food truck) | Uniform | Production time has no central tendency |
| Counter order time | Truncated normal | All models |
| Kiosk order time | Truncated normal | Hybrid models only |
| Patience threshold | Normal (untruncated) | Clamp negative draws to 0 |
| Group size | Weighted discrete | Unchanged |

Use `scipy.stats.truncnorm` for all truncated normal draws.

---

## 4. New and Updated Seating Strategies

### Existing strategies (unchanged)
- `fifo_fit`
- `best_fit`
- `smallest_table_fit`
- `strict_fifo_fit`

### New strategies
- `first_available` — assigns the group at the head of the queue to the next free table regardless of size fit. A size-2 group may occupy a 6-seat table. No waste minimisation.
- `exact_match` — a group can only be seated at a table whose seat count equals the group size exactly. If no exact match is free, the group waits even if larger tables are available. The simulation detects and logs starvation cases where no exact match table exists in the inventory for a given group size.

---

## 5. Event Types

The event loop is extended with the following event types:

| Event | Description |
|---|---|
| `ARRIVAL` | Group enters the system, patience timer starts |
| `ORDER_START` | Group reaches front of ordering queue, server/kiosk assigned |
| `ORDER_COMPLETE` | Ordering finishes, group moves to seating queue |
| `SEATED` | Table assigned, dining timer starts |
| `DEPARTURE` | Dining complete, table released, seating strategy re-evaluated |
| `ABANDONMENT` | Patience expired, group removed from whichever stage they are in |
| `RESERVATION_HOLD` | Table removed from walk-in pool before scheduled reservation |
| `RESERVATION_RELEASE` | Table returned to walk-in pool after hold window expires without arrival |

**Tie-breaking rule (unchanged):** At equal timestamps, `DEPARTURE` events are processed before `ARRIVAL` events. `RESERVATION_RELEASE` is processed before `ARRIVAL` at the same timestamp.

---

## 6. Abandonment Model

Each group is assigned a `patience_threshold` at arrival, sampled from `Normal(patience_threshold_mean, patience_threshold_sd)`. Negative draws are clamped to 0.

The threshold applies to total elapsed wait time from arrival, spanning both the ordering and seating stages. There is no separate patience budget per stage.

When a group's elapsed wait reaches their threshold, they are removed from their current queue and logged as abandoned. The log records which stage they abandoned at (ordering or seating).

`abandonment_rate_at_threshold` from the teammate's test cases is not implemented. The per-group threshold model is retained as it is more principled.

---

## 7. Reservation System

When `reservation_policy` is `"hybrid_allocation"`:

- At simulation initialisation, `floor(total_tables * reserved_table_percent)` tables are flagged as reserved. Reserved tables are selected by preferring larger tables first, since reservations skew toward larger groups in practice.
- Reserved groups are pre-injected into the event queue as `ARRIVAL` events at their scheduled time. They skip Stage 1 (ordering) and enter the seating queue directly.
- A `RESERVATION_HOLD` event fires `reservation_hold_before_min` minutes before each reserved group's scheduled arrival, locking the table.
- If the reserved group does not arrive, a `RESERVATION_RELEASE` event fires `reservation_hold_after_min` minutes after the scheduled arrival, returning the table to walk-in availability.
- Walk-in groups cannot be seated at reserved tables while they are held.

---

## 8. Output Statistics

### Existing outputs (unchanged)
- Average, min, max total wait time
- Table utilization per table size and overall
- Peak queue length
- Groups served, rejected, abandoned

### New outputs
- Wait time broken down by stage: ordering wait and seating wait reported separately
- Per-group-size wait time breakdown
- Server utilization rate (time servers are occupied / total simulation time)
- Kiosk utilization rate
- Abandonment breakdown: abandoned at ordering stage vs seating stage
- Reservation statistics (when applicable): groups served from reservation pool, no-show count, tables released early

---

## 9. Updated Business Model Presets

All six presets are updated to include the new parameters.

```python
"fast_food": BusinessModel(
    name="fast_food",
    queue_type="single_queue",
    strategy_name="fifo_fit",
    tables=[TableInventory(seats=2, count=8), TableInventory(seats=4, count=4)],
    generator_profile=GeneratorProfile(
        min_group_size=1,
        max_group_size=4,
        group_size_weights={1: 0.35, 2: 0.35, 3: 0.1, 4: 0.2},
        min_dining_duration=8,
        max_dining_duration=30,
        dining_duration_mean=18,
        dining_duration_sd=5,
    ),
    servers=3,
    ordering_type="counter_only",
    counter_order_time_min=1,
    counter_order_time_max=4,
    counter_order_time_mean=2,
    counter_order_time_sd=0.8,
    kiosks=0,
    reservation_policy="none",
    patience_threshold_mean=15.0,
    patience_threshold_sd=5.0,
    notes="Quick turnover. Counter ordering is fast. No reservations.",
),

"fine_dining": BusinessModel(
    name="fine_dining",
    queue_type="queue_by_group_size",
    strategy_name="best_fit",
    tables=[TableInventory(seats=2, count=5), TableInventory(seats=4, count=5), TableInventory(seats=6, count=3)],
    generator_profile=GeneratorProfile(
        min_group_size=2,
        max_group_size=6,
        group_size_weights={2: 0.35, 3: 0.18, 4: 0.25, 5: 0.14, 6: 0.08},
        min_dining_duration=75,
        max_dining_duration=150,
        dining_duration_mean=105,
        dining_duration_sd=18,
    ),
    servers=4,
    ordering_type="counter_only",
    counter_order_time_min=3,
    counter_order_time_max=10,
    counter_order_time_mean=6,
    counter_order_time_sd=2,
    kiosks=0,
    reservation_policy="hybrid_allocation",
    reserved_table_percent=0.5,
    reservation_hold_before_min=15,
    reservation_hold_after_min=15,
    patience_threshold_mean=42.0,
    patience_threshold_sd=15.0,
    notes="Slow turnover. Tableside ordering by staff. Half tables reserved.",
),

"casual_dining": BusinessModel(
    name="casual_dining",
    queue_type="single_queue",
    strategy_name="fifo_fit",
    tables=[TableInventory(seats=2, count=5), TableInventory(seats=4, count=6), TableInventory(seats=6, count=2)],
    generator_profile=GeneratorProfile(
        min_group_size=1,
        max_group_size=6,
        group_size_weights={1: 0.12, 2: 0.28, 3: 0.18, 4: 0.26, 5: 0.1, 6: 0.06},
        min_dining_duration=40,
        max_dining_duration=90,
        dining_duration_mean=60,
        dining_duration_sd=12,
    ),
    servers=3,
    ordering_type="counter_only",
    counter_order_time_min=2,
    counter_order_time_max=6,
    counter_order_time_mean=3,
    counter_order_time_sd=1,
    kiosks=0,
    reservation_policy="none",
    patience_threshold_mean=24.0,
    patience_threshold_sd=8.0,
    notes="Balanced turnover. Tableside ordering. No reservations.",
),

"cafe": BusinessModel(
    name="cafe",
    queue_type="single_queue",
    strategy_name="smallest_table_fit",
    tables=[TableInventory(seats=1, count=4), TableInventory(seats=2, count=6), TableInventory(seats=4, count=3)],
    generator_profile=GeneratorProfile(
        min_group_size=1,
        max_group_size=4,
        group_size_weights={1: 0.42, 2: 0.34, 3: 0.14, 4: 0.1},
        min_dining_duration=25,
        max_dining_duration=60,
        dining_duration_mean=38,
        dining_duration_sd=8,
    ),
    servers=2,
    ordering_type="hybrid",
    counter_order_time_min=1,
    counter_order_time_max=4,
    counter_order_time_mean=2,
    counter_order_time_sd=0.7,
    kiosks=1,
    kiosk_usage_percent=0.4,
    kiosk_order_time_min=1,
    kiosk_order_time_max=3,
    kiosk_order_time_mean=1.5,
    kiosk_order_time_sd=0.5,
    reservation_policy="none",
    patience_threshold_mean=12.0,
    patience_threshold_sd=4.0,
    notes="Solo and pair dominant. Mix of counter and self-service ordering. No reservations.",
),

"food_truck": BusinessModel(
    name="food_truck",
    queue_type="single_queue",
    strategy_name="strict_fifo_fit",
    tables=[TableInventory(seats=1, count=3)],
    generator_profile=GeneratorProfile(
        min_group_size=1,
        max_group_size=1,
        group_size_weights={1: 1.0},
        min_dining_duration=1,
        max_dining_duration=5,
        dining_duration_mean=3,
        dining_duration_sd=1,
    ),
    servers=1,
    ordering_type="counter_only",
    counter_order_time_min=1,
    counter_order_time_max=4,
    counter_order_time_mean=2,
    counter_order_time_sd=0.8,
    kiosks=0,
    reservation_policy="none",
    patience_threshold_mean=7.0,
    patience_threshold_sd=3.0,
    notes="Single server. Order time models production time. Slot occupancy models pickup wait.",
),

```

---

## 10. JSON Scenario Format (Updated)

The saved scenario JSON is extended to include all new fields. Example partial structure:

```json
{
  "business_model": {
    "name": "casual_dining",
    "queue_type": "single_queue",
    "strategy": "fifo_fit",
    "tables": [
      {"seats": 2, "count": 5},
      {"seats": 4, "count": 6},
      {"seats": 6, "count": 2}
    ],
    "generator_profile": {
      "min_group_size": 1,
      "max_group_size": 6,
      "group_size_weights": {"1": 0.12, "2": 0.28, "3": 0.18, "4": 0.26, "5": 0.1, "6": 0.06},
      "min_dining_duration": 40,
      "max_dining_duration": 90,
      "dining_duration_mean": 60,
      "dining_duration_sd": 12
    },
    "servers": 3,
    "ordering_type": "counter_only",
    "counter_order_time_min": 2,
    "counter_order_time_max": 6,
    "counter_order_time_mean": 3,
    "counter_order_time_sd": 1,
    "kiosks": 0,
    "reservation_policy": "none",
    "patience_threshold_mean": 24.0,
    "patience_threshold_sd": 8.0
  },
  "seed": 42,
  "arrivals": [
    {
      "arrival_time": 0,
      "group_size": 3,
      "dining_duration": 55,
      "patience": 22,
      "is_reservation": false
    },
    {
      "arrival_time": 5,
      "group_size": 2,
      "dining_duration": 48,
      "patience": 30,
      "is_reservation": true,
      "scheduled_time": 5
    }
  ]
}
```

---

## 11. What Does Not Change

- Core event loop structure
- Existing four seating strategies
- `single_queue` and `queue_by_group_size` queue disciplines
- GUI layer structure and navigation flow
- Results export as plain-text report
- Queue cap of 99 entries
- Departure-before-arrival tie-breaking rule
- Rejection of groups larger than the largest table
