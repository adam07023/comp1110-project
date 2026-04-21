````markdown
# Restaurant Queue Simulation

A discrete-event restaurant queue simulator written in Python, with both a CLI and PyQt6 GUI interface.

## Features

- Built-in business model presets:
  - `fast_food`
  - `fine_dining`
  - `casual_dining`
  - `cafe`
  - `food_truck`
- Explicit arrival-event simulation with integer minute timestamps
- Multiple table sizes per scenario
- Queue organizations:
  - `single_queue`
  - `queue_by_group_size`
- Seating strategies:
  - `fifo_fit`
  - `best_fit`
  - `smallest_table_fit`
  - `strict_fifo_fit`
- Per-group patience thresholds — groups leave the queue if wait exceeds their sampled threshold
- Reproducible random scenario generation using seeds
- Scenario export/import as JSON (model parameters + queue entries)
- Results export as human-readable plain-text report

## Install GUI library and Run GUI

```bash
python3 pip install PyQt6
python3 main.py gui
```
## Run in CLI
```bash
python3 main.py list-models
python3 main.py write-example
python3 main.py generate
python3 main.py run

```
## Scenario Format

Scenarios are stored as JSON files containing the business model parameters and the ordered list of queue entries. Example:

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
    "generator_profile": {
      "min_group_size": 1,
      "max_group_size": 4,
      "group_size_weights": {"1": 0.35, "2": 0.35, "3": 0.1, "4": 0.2},
      "min_dining_duration": 8,
      "max_dining_duration": 30
    },
    "patience_threshold_mean": 15.0,
    "patience_threshold_sd": 5.0
  },
  "seed": 42,
  "arrivals": [
    {"arrival_time": 0, "group_size": 2, "dining_duration": 18, "patience": 14},
    {"arrival_time": 3, "group_size": 1, "dining_duration": 12, "patience": 11},
    {"arrival_time": 5, "group_size": 4, "dining_duration": 25, "patience": 20}
  ]
}
```

## Notes

- Time is represented as integer minutes from simulation start.
- Groups larger than the largest table capacity are rejected and recorded.
- Departure events at a timestamp are processed before arrivals at the same timestamp.
- Groups whose wait time exceeds their patience threshold are removed from the queue and recorded as departed without being seated.
````