# Simulation Spec v2
## Restaurant Queue Simulation — Case Study Design

**Status:** This is an update to the previous simulation spec, which defined 4 factorial interaction pairs (F1–F4) and 5 single-factor OAT pairs (S1–S5) run by the automated agent. This version expands the factorial design to 6 interaction pairs, incorporates all 5 original teammate scenarios as sub-cases, adds a decision gate between OAT and factorial testing, and clarifies the replication and metric recording procedure. Repository structure changes are specified in Section 6. 

---

## 1. Motivation

The original teammate design tested each factor in isolation (OAT) and in selected two-factor interactions. The factorial design is implemented for two reasons:

First, the simulation has six seating strategies, four arrival modes, two queue types, and multiple server configurations. Testing only one or two values per factor artificially limits the analytical scope when the automation infrastructure already supports broader testing.

Second, single-factor tests cannot reveal whether the effect of one factor depends on another. For example, `best_fit` may outperform `fifo_fit` only when table inventory is heterogeneous, or kiosk parallelism may only benefit throughput when customers are impatient. These interaction effects are the most analytically valuable findings and require factorial design to surface.

The 5 original teammate scenarios are retained as sub-cases within the OAT step rather than discarded.

---

## 2. Parameters

### 2.1 Experimental Factors
Parameters varied across scenario runs:

- `strategy` — seating decision rule (`fifo_fit`, `best_fit`, `smallest_table_fit`, `strict_fifo_fit`, `first_available`, `exact_match`)
- `queue_type` — (`single_queue`, `queue_by_group_size`)
- `tables` — table inventory composition (small-heavy vs large-heavy)
- `arrival_pattern` — (`uniform`, `left_skewed`, `centered`, `right_skewed`)
- `servers` — number of counter ordering staff
- `ordering_type` — (`counter_only`, `hybrid`)
- `kiosk_usage_percent` — proportion routed to kiosks when `ordering_type=hybrid`
- `patience_mean` — mean patience threshold controlling abandonment rate
- `reservation_policy` — (`none`, `hybrid_allocation`)
- `reserved_table_percent` — fraction of tables held for reservations

### 2.2 Nuisance Parameters (Held Constant)
Fixed at casual dining preset defaults across all scenarios unless explicitly noted:

- All distribution SDs (`dining_duration_sd`, `order_time_sd`, `patience_sd`)
- Dining duration mean (`dining_duration_mean`)
- `reservation_hold_before_min` = 10, `reservation_hold_after_min` = 10
- `min/max` bounds for dining duration, order time, group size
- `group_size_weights`
- `kiosk_order_time_mean/sd` and `counter_order_time_mean/sd` (note that the kiosk order time should have a slightly higher constant mean and sd than counter order time)
---

## 3. Baseline Configuration

All scenarios derive from one canonical baseline using a modified casual dining preset with seed=42. Any run that is not the baseline changes only the factors explicitly listed for that scenario. Everything else is inherited from this baseline unchanged.

Fine dining preset is used as the base for Pair 5 (reservation policy) since reservations are not realistic for casual dining.

```json
{
  "base_model": "casual_dining",
  "seed": 42,
  "queue_type": "single_queue",
  "strategy": "fifo_fit",
  "arrival_pattern": "centered",
  "tables": [{"seats": 2, "count": 5}, {"seats": 4, "count": 6}, {"seats": 6, "count": 2}],
  "servers": 3,
  "ordering_type": "counter_only",
  "patience_mean": 24.0,
  "reservation_policy": "none"
}
```

---

## 4. Experimental Design

### Step 1 — Classify Parameters
Parameters are classified as experimental factors (Section 2.1) or nuisance parameters (Section 2.2) before any runs are executed.

### Step 2 — Single-Factor OAT Pairs
Establish the main effect of each experimental factor in isolation. Each pair holds all other parameters at baseline and varies exactly one factor across Run A and Run B.

These incorporate all 5 original teammate scenarios.

| Pair | Factor | Run A | Run B | Teammate origin |
|---|---|---|---|---|
| S1 | Strategy | `fifo_fit` | `best_fit` | Scenario 1 |
| S2 | Queue type | `single_queue` | `queue_by_group_size` | Scenario 2 |
| S3 | Ordering configuration | `counter_only`, 3 counters | `hybrid`, 1 counter + 3 kiosks | Scenario 3 |
| S4 | Server count | 2 servers | 4 servers | Scenario 4 (in this case server denotes counters) |
| S5 | Reservation policy | `none` | `hybrid_allocation`, 50% reserved | Scenario 5 |
| S6 | Patience | low mean(10) | high mean(30) | Scenario 6 |
| S7 | Table Inventory | small-heavy (8×2, 4×4) | large-heavy (2×2, 4×4, 4×6) | Scenario 7 |
| S8 | Arrival Pattern | uniform | right_skewed | Scenario 8 |


### Step 3 — Decision Gate
Before proceeding to factorial pairs, verify that each experimental factor produced a non-trivial main effect in Step 2. A factor with no measurable effect on any metric under OAT does not belong in a factorial interaction. Document which factors pass this gate and which do not.

Threshold for non-trivial effect: at least one metric changes by more than one standard deviation across the 3 replicates.

### Step 4 — Factorial Interaction Pairs
Each factorial pair is a 2×2 design: two levels of factor A crossed with two levels of factor B, producing 4 runs per pair. The question for each pair is whether the effect of factor A on outcomes depends on the level of factor B.

**Pair F1 — Strategy × Table inventory**
Question: Does `best_fit` outperform `fifo_fit` more when table inventory is heterogeneous?

| Run | Strategy | Tables |
|---|---|---|
| A | `fifo_fit` | small-heavy (8×2, 4×4) |
| B | `best_fit` | small-heavy (8×2, 4×4) |
| C | `fifo_fit` | large-heavy (2×2, 4×4, 4×6) |
| D | `best_fit` | large-heavy (2×2, 4×4, 4×6) |

If the B−A gap is larger than the D−C gap, seating strategy matters more when tables are heterogeneous.

---

**Pair F2 — Queue type × Arrival pattern**
Question: Does separating queues by size produce greater benefit when arrivals are skewed toward later-arriving large groups?

| Run | Queue type | Arrival pattern |
|---|---|---|
| A | `single_queue` | `uniform` |
| B | `queue_by_group_size` | `uniform` |
| C | `single_queue` | `right_skewed` |
| D | `queue_by_group_size` | `right_skewed` |

If the B−A gap is larger than the D−C gap, size-based queuing is more valuable when large groups arrive late.

---

**Pair F3 — Ordering configuration × Patience**
Question: Does the parallelism benefit of kiosks (more simultaneous ordering slots despite slower per-order time) materialise specifically when customers are impatient?

| Run | Ordering type | Patience mean |
|---|---|---|
| A | `counter_only`, 3 counters | low (10 min) |
| B | `hybrid`, 1 counter + 3 kiosks | low (10 min) |
| C | `counter_only`, 3 counters | high (30 min) |
| D | `hybrid`, 1 counter + 3 kiosks | high (30 min) |

If the B−A improvement is larger than D−C, kiosk parallelism matters most when customers are impatient.

---

**Pair F4 — Server count × Patience**
Question: Does adding servers (counters) improve service level more when customers are impatient, and does the benefit plateau when customers are tolerant?

| Run | Servers (counters) | Patience mean |
|---|---|---|
| A | 2 | low (10 min) |
| B | 4 | low (10 min) |
| C | 2 | high (30 min) |
| D | 4 | high (30 min) |

If the B−A improvement is larger than D−C, server count matters most under time pressure. If gaps are equal, patience and server count are independent.

---

**Pair F5 — Reservation policy × Table scarcity** (fine dining base)
Question: Does hybrid reservation improve overall throughput more when tables are scarce?

| Run | Reservation policy | Tables |
|---|---|---|
| A | `none` | generous (5×2, 5×4, 3×6) |
| B | `hybrid_allocation` 50% | generous (5×2, 5×4, 3×6) |
| C | `none` | tight (3×2, 3×4, 2×6) |
| D | `hybrid_allocation` 50% | tight (3×2, 3×4, 2×6) |

If reservations hurt walk-in service level more under tight inventory, this reveals the operational cost of reservation commitments under capacity constraints.

---

**Pair F6 — Strategy × Queue type**
Question: Does the advantage of a smarter seating strategy diminish when groups are already pre-sorted by size into separate queues?

| Run | Strategy | Queue type |
|---|---|---|
| A | `fifo_fit` | `single_queue` |
| B | `best_fit` | `single_queue` |
| C | `fifo_fit` | `queue_by_group_size` |
| D | `best_fit` | `queue_by_group_size` |

If the B−A gap shrinks in C vs D, size-based queuing partially substitutes for intelligent seating strategy.

---

### Step 5 — Replication
Run every configuration (baseline, all OAT runs, all factorial runs) with k=3 seeds: 42, 123, 999. Hold all parameters constant across replicates. Report mean and range across replicates for each metric. Do not interpret a finding as meaningful if it does not hold across all 3 seeds.

### Step 6 — Metric Recording
Record the following for every run:

- Average, min, max total wait time
- Average ordering wait time
- Service level at model-specific threshold (% groups seated within threshold minutes)
- Table utilisation per table size and overall
- Max queue length per queue lane
- Server utilisation rate
- Groups served, abandoned at ordering stage, abandoned at seating stage, rejected
- Peak queue length at ordering and seating stages separately

### Step 7 — Analysis and Implications
For each OAT pair: state the main effect direction and magnitude, note whether it held across all 3 seeds, and state the real-world operational implication in one sentence.

For each factorial pair: state whether an interaction effect exists (does the effect of A depend on B), quantify the interaction if present, and state what a restaurant operator should conclude.

---

## 5. Automated Runner Specification

The runner script loads all scenario configs from a scenarios directory, executes each run, collects metrics, and writes outputs. The following structure is required:

**Scenario config format:**
Each scenario is a JSON file specifying the base model, parameter overrides for each run, seed list, and metric direction assertions for automated validation.

```json
{
  "pair_id": "F1",
  "description": "Strategy vs Table inventory",
  "base_model": "casual_dining",
  "seeds": [42, 123, 999],
  "runs": [
    {
      "run_id": "A",
      "overrides": {"strategy": "fifo_fit", "tables": [{"seats": 2, "count": 8}, {"seats": 4, "count": 4}]}
    },
    {
      "run_id": "B",
      "overrides": {"strategy": "best_fit", "tables": [{"seats": 2, "count": 8}, {"seats": 4, "count": 4}]}
    },
    {
      "run_id": "C",
      "overrides": {"strategy": "fifo_fit", "tables": [{"seats": 2, "count": 2}, {"seats": 4, "count": 4}, {"seats": 6, "count": 4}]}
    },
    {
      "run_id": "D",
      "overrides": {"strategy": "best_fit", "tables": [{"seats": 2, "count": 2}, {"seats": 4, "count": 4}, {"seats": 6, "count": 4}]}
    }
  ],
  "assertions": [
    {"metric": "avg_wait", "direction": "B < A"},
    {"metric": "table_utilization", "direction": "B > A"}
  ]
}
```

**Runner output per pair:**
- Side-by-side metric table across all runs and seeds
- Mean and range per metric per run
- Assertion pass/fail per metric direction

---

## 6. Repository Structure Changes

The current "Scenario analysis" repository contains: `inputs/`, `outputs/`, `insights/`, `summaries/` (CSV metrics), `README.md`.

The following changes are required:

**Add `scenarios/` folder**
Contains one JSON config file per scenario pair (e.g. `S1_strategy_oat.json`, `F1_strategy_x_tables.json`). These are the machine-readable scenario definitions used by the runner.

**Add `runner.py`**
Automated script that reads all files in `scenarios/`, executes each run with each seed, writes results to `outputs/` and CSVs to `summary/`, and prints assertion results to console.

**Update `inputs/`**
The canonical baseline configuration should be saved as `baseline_casual_dining_seed42.json`. Each scenario pair's shared arrival queue (generated once from baseline) should be saved as a separate input file referenced by all runs in that pair.

**Update `README.md`**
Add a section describing the scenario runner: how to execute it, what the scenario config format means, and where outputs are written. Document each scenario pair's purpose in one sentence.

**No changes required to `outputs/` or `insights/`**
These are populated by the runner and their current structure is sufficient.
