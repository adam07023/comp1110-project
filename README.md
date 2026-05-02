# Restaurant Queue Simulation

A Python discrete-event simulator for Topic C: Restaurant Queue Simulation. The program models customer arrivals, table capacity, ordering capacity, queue rules, patience limits, reservations, and seating decisions, then reports operational metrics that help compare restaurant settings.

The project can be used through either a command-line interface or a PyQt6 graphical interface.

## Language, environment, and build

| Item | Details |
|------|---------|
| **Language** | Python **3** (uses type hints and `list[str]` syntax; use **3.10+** for best compatibility). |
| **Execution** | **Interpreted** — no compilation step. Run modules with `python3`. |
| **Core runtime** | Standard library plus this repository’s source; simulations and CLI work without extra packages. |
| **Optional** | **PyQt6** for `python3 main.py gui`; **scipy** for faster truncated-normal sampling (otherwise bounded rejection sampling). |

Install optional packages when needed:

```bash
python3 -m pip install PyQt6 scipy
```

Persistence and interchange use **text**, **JSON**, and **CSV** (and Markdown reports for batch analysis). No database.

## Features

- Built-in restaurant presets: `fast_food`, `fine_dining`, `casual_dining`, `cafe`, and `food_truck`.
- Custom restaurant setup in the GUI, including table inventory, queue type, seating strategy, arrival pattern, servers (counters + kiosks), order-time distribution, reservations, patience, and dining-duration distribution.
- Queue types:
  - `single_queue`: all waiting groups share one queue.
  - `queue_by_group_size`: waiting groups are split into coarse queues `1-2`, `3-4`, and `5+`.
- Seating strategies:
  - `fifo_fit`
  - `best_fit`
  - `smallest_table_fit`
  - `strict_fifo_fit`
  - `first_available`
  - `exact_match`
- Random scenario generation with seeded reproducibility.
- File input/output using text scenario files and JSON scenario files.
- Validation for bad files, invalid JSON, missing fields, invalid queue rows, impossible reservations, and invalid numerical bounds.
- Result reports with aggregate wait metrics, **average** wait by group size, queue peaks, per-queue maximum lengths, service level, table utilization, server utilization, abandonment counts, and reservation statistics.

## Setup

**CLI-only:** You do not need PyQt6 unless you run `python3 main.py gui`. Listing models, writing or generating scenarios, running simulations, and running automated analysis all work with the standard library plus the simulation code (and optional `scipy`).

## Sample inputs and tests

- **`examples/`** — sample **text** scenarios (and similar fixtures) you can pass to `main.py run --scenario …`. Use `main.py write-example` or `generate` to create additional scenarios.
- **`tests/`** — automated **sample test cases** (`unittest`): engine behavior, strategies, loaders, validation, CLI, and analysis runners. Run everything with:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Topic-specific batch experiments are also configured under `suite_analysis/scenario_suite.json` and `scenario_analysis/scenarios/` (see `specifications/`).

## Run The GUI

```bash
python3 main.py gui
```

In the GUI, choose a preset or customize a restaurant, generate or edit arrivals, run the simulation, and optionally save the scenario or result report.

## Run The CLI

List available presets (queue, strategy, tables, counters/kiosks, patience, arrival pattern, reservations):

```bash
python3 main.py list-models
```

Write an example scenario:

```bash
python3 main.py write-example --model fast_food --output examples/fast_food_sample.txt
```

Generate a random scenario:

```bash
python3 main.py generate --model cafe --output examples/cafe_generated.txt --seed 42 --arrival-count 20 --duration 90
```

Run a scenario and print results:

```bash
python3 main.py run --scenario examples/fast_food_sample.txt
```

Run a scenario and save results:

```bash
python3 main.py run --scenario examples/fast_food_sample.txt --output examples/fast_food_result.txt
```

`run` accepts either a **text** scenario (`.txt`) or a **JSON** scenario (`.json`); the loader picks based on the file extension.

### Automated scenario analysis (`analyze`)

The `suite_analysis/` package runs every experiment in a JSON suite across replicated seeds, aggregates metrics, checks directional expectations, and writes Markdown/CSV reports:

```bash
python3 main.py analyze --config suite_analysis/scenario_suite.json --output-dir suite_analysis/output
```

Useful options:

- `--seeds 42,101` — override the suite’s default seed list (comma-separated integers).
- `--write-scenarios` — also write each generated scenario JSON under the output directory.
- `--strict-expectations` — exit with status 2 if an expected metric direction is not met (prints `All metric expectations met.` when checks pass).

### Paired scenario analysis (spec v2)

For the teammate paired-design workflow (A/B configs per scenario, shared arrivals where required, OAT and factorial summaries), run the dedicated runner. It writes run artifacts under `scenario_analysis/outputs/`, shared/baseline JSON under `scenario_analysis/inputs/`, summary CSVs under `scenario_analysis/summaries/`, and a Markdown report under `scenario_analysis/insights/`:

```bash
python3 scenario_analysis/runner.py
```

See `specifications/scenario_analysis_spec_v2.md` for the full procedure.

## Core files (source map)

- `main.py` — CLI entry point (`list-models`, `write-example`, `generate`, `run`, `analyze`, `gui`) and helpers shared with the GUI.
- `gui_main.py` — starts the PyQt application (`main.py gui`).
- `gui/app.py` — main window: presets, queue editor, load/save JSON, run simulation, view results.
- `domain/models.py` — scenario, arrivals, tables, statistics, simulation result containers.
- `domain/events.py` — discrete-event log records.
- `domain/business_model.py` — preset / generator configuration types.
- `domain/statistics.py` — aggregates metrics after a run.
- `presets/builtins.py` — built-in restaurant models.
- `generation/randomizer.py` — random scenarios and sampling helpers.
- `generation/validators.py` — validates scenarios before simulation.
- `generation/seed_store.py` — seed metadata for reading/writing scenarios.
- `simulation/engine.py` — discrete-event simulation loop.
- `simulation/queue_manager.py` — queue data structures (`single_queue`, `queue_by_group_size`).
- `simulation/strategies.py` — seating assignment strategies.
- `simulation/allocator.py` — expands table inventory rows into individual tables.
- `fileio/scenario_loader.py`, `fileio/scenario_writer.py` — text scenario I/O.
- `fileio/json_scenario_io.py` — JSON scenario I/O.
- `fileio/result_writer.py` — text result report I/O.
- `suite_analysis/config.py` — loads and validates `scenario_suite.json`.
- `suite_analysis/scenario_builder.py` — builds `Scenario` objects for each experiment run.
- `suite_analysis/runner.py` — runs the full suite over seeds (`main.py analyze`).
- `suite_analysis/report_writer.py` — CSV / JSON / Markdown aggregate reports.
- `scenario_analysis/runner.py` — spec v2 paired scenarios, OAT/factorial summaries (separate from `analyze`).
- `tests/` — unit tests (see **Sample inputs and tests** above).
- `specifications/` — design and analysis specs for the topic.

## Scenario Model

Each customer group has:

- `group_id`
- `arrival_time`
- `group_size`
- `dining_duration`
- optional `patience`
- optional reservation fields

Each restaurant setting has:

- table inventory (`seats`, `count`)
- queue type
- seating strategy
- server count (`servers` includes both counters and kiosks)
- order-time distribution
- patience distribution
- reservation policy

For most restaurants, groups first wait for an ordering resource (counter or kiosk), complete ordering, then wait for a suitable table. For `food_truck`, ordering is the service itself: the two 1-seat table slots represent the service positions, and `dining_duration` represents order/pickup service time.

## JSON Scenario Example

```json
{
  "business_model": {
    "name": "fast_food",
    "queue_type": "single_queue",
    "strategy": "fifo_fit",
    "tables": [
      {"seats": 2, "count": 8},
      {"seats": 4, "count": 4}
    ],
    "counters": 1,
    "kiosks": 3,
    "kiosk_usage_percent": 0.75,
    "counter_order_time_min": 1,
    "counter_order_time_max": 4,
    "counter_order_time_mean": 2,
    "counter_order_time_sd": 0.8,
    "reservation_policy": "none",
    "patience_threshold_mean": 15.0,
    "patience_threshold_sd": 5.0
  },
  "seed": 42,
  "generated": true,
  "arrivals": [
    {"group_id": "G1", "arrival_time": 0, "group_size": 2, "dining_duration": 18, "patience": 14},
    {"group_id": "G2", "arrival_time": 3, "group_size": 1, "dining_duration": 12, "patience": 11},
    {"group_id": "G3", "arrival_time": 5, "group_size": 4, "dining_duration": 25, "patience": 20}
  ]
}
```

## Output Metrics

The result report includes:

- Groups served, rejected, and total groups.
- Average, minimum, and maximum total wait time (arrival to seating).
- Average wait time by group size (same arrival-to-seating definition).
- Average ordering wait and average ordering wait by group size.
- Overall maximum and minimum queue length.
- Per-queue maximum length (`all`, or `1-2`, `3-4`, `5+` for grouped queues).
- Table utilization and server utilization.
- Service level: share of seated groups whose total wait is within a **per-preset** threshold (minutes): `food_truck` 5, `cafe` 8, `fast_food` 10, `casual_dining` 20, `fine_dining` 30; unrecognized model names use 10. The report includes the applied value as `service_level_threshold`.
- Abandonments during ordering/seating.
- Reservation groups served, no-shows, and released reserved tables.

## Notes

- Time is represented as integer minutes from simulation start.
- Groups larger than the largest table capacity are rejected.
- Departure events at a timestamp are processed before arrivals at the same timestamp.
- Groups whose wait exceeds their patience threshold leave and are recorded as rejected due to patience.
- In JSON scenarios, you can provide either `servers` (combined ordering capacity) or explicit `counters` and `kiosks`.