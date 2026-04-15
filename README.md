# Restaurant Queue Simulation

A CLI-first discrete-event restaurant queue simulator written in Python.

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
- Reproducible random scenario generation using seeds
- Sectioned plain-text scenario and result files

## Run

```bash
python3 main.py list-models
python3 main.py write-example --model fast_food --output examples/fast_food_sample.txt
python3 main.py generate --model cafe --output examples/generated_seed_example.txt --seed 42 --arrival-count 20 --duration 180
python3 main.py run --scenario examples/fast_food_sample.txt --output examples/fast_food_result.txt
```

## Scenario Format

```txt
[business_model]
name=fast_food

[queue]
type=single_queue
strategy=fifo_fit

[tables]
# seats_per_table, table_count
2,4
4,6

[arrivals]
# arrival_time, group_size, dining_duration
0,2,18
3,1,12
5,4,25

[seed]
value=42
generated=false
```

## Notes

- Time is represented as integer minutes from simulation start.
- Groups larger than the largest table capacity are rejected and recorded.
- Departure events at a timestamp are processed before arrivals at the same timestamp.
