# Restaurant Queue Simulation

A Python discrete-event simulator for Topic C: Restaurant Queue Simulation. The program models customer arrivals, table capacity, ordering capacity, queue rules, patience limits, reservations, and seating decisions, then reports operational metrics that help compare restaurant settings.

The project can be used through either a command-line interface or a PyQt6 graphical interface.

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
- Result reports with total wait time, group-size wait breakdowns, queue peaks, per-queue maximum lengths, service level, table utilization, server utilization, abandonment counts, and reservation statistics.

## Setup

Install optional GUI/scientific dependencies:

```bash
python3 -m pip install PyQt6 scipy
```

`scipy` is optional but improves truncated-normal sampling. Without it, the program falls back to bounded rejection sampling.

## Run The GUI

```bash
python3 main.py gui
```

In the GUI, choose a preset or customize a restaurant, generate or edit arrivals, run the simulation, and optionally save the scenario or result report.

## Run The CLI

List available presets:

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

## Core Files

- `main.py`: command-line entry point and GUI-facing helper functions.
- `gui/app.py`: PyQt6 interface for choosing models, building queues, loading/saving JSON, and viewing results.
- `domain/models.py`: scenario, arrival, table, event, and statistics data structures.
- `domain/business_model.py`: preset/custom restaurant configuration structure.
- `presets/builtins.py`: built-in restaurant models.
- `generation/randomizer.py`: random arrival, group size, dining duration, and patience generation.
- `generation/validators.py`: scenario validation.
- `simulation/engine.py`: discrete-event simulation loop.
- `simulation/queue_manager.py`: single queue and coarse group-size queue implementations.
- `simulation/strategies.py`: table assignment strategies.
- `fileio/scenario_loader.py` and `fileio/scenario_writer.py`: text scenario input/output.
- `fileio/json_scenario_io.py`: JSON scenario input/output.
- `fileio/result_writer.py`: text result report output.
- `tests/`: unit tests for generation, engine behavior, queue logic, validation, file formats, and strategies.

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
- Average, minimum, and maximum total wait time.
- Total wait time by group size, measured from arrival to seating.
- Average ordering wait and ordering wait by group size.
- Overall maximum and minimum queue length.
- Per-queue maximum length (`all`, or `1-2`, `3-4`, `5+` for grouped queues).
- Table utilization and server utilization.
- Service level: percentage of seated groups seated within the configured threshold (10 minutes by default).
- Abandonments during ordering/seating.
- Reservation groups served, no-shows, and released reserved tables.

## Notes

- Time is represented as integer minutes from simulation start.
- Groups larger than the largest table capacity are rejected.
- Departure events at a timestamp are processed before arrivals at the same timestamp.
- Groups whose wait exceeds their patience threshold leave and are recorded as rejected due to patience.
- In JSON scenarios, you can provide either `servers` (combined ordering capacity) or explicit `counters` and `kiosks`.