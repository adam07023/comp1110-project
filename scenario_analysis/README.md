# Scenario Analysis

This directory contains the report-ready restaurant scenario analysis. The v2 workflow follows `scenario_analysis_spec_v2.md` and keeps its configs, runner, inputs, outputs, summaries, and insights together.

## How To Run V2

From the project root:

```bash
python3 "scenario_analysis/runner.py"
```

The runner reads every JSON file in `scenarios/`, executes each run with seeds `42`, `123`, and `999`, writes run outputs to `outputs/`, and writes CSV/report summaries to `summaries/` and `insights/`.

## V2 Config Format

Each file in `scenarios/` describes one pair:

- `pair_id`: pair label such as `S1` or `F1`.
- `kind`: `oat` for single-factor pairs or `factorial` for 2x2 interaction pairs.
- `description`: one-sentence purpose.
- `base_model`: built-in model used as the base.
- `seeds`: replication seeds.
- `runs`: list of run IDs and parameter overrides.
- `assertions`: expected metric directions such as `B < A`.

## V2 Scenario Pairs

- `S1`: seating strategy, `fifo_fit` vs `best_fit`.
- `S2`: queue type, `single_queue` vs `queue_by_group_size`.
- `S3`: ordering configuration, counter-only vs hybrid kiosks.
- `S4`: counter/server count, 2 vs 4 counters.
- `S5`: reservation policy, none vs 50% hybrid allocation.
- `S6`: patience mean, 10 vs 30 minutes.
- `S7`: table inventory, small-heavy vs large-heavy.
- `S8`: arrival pattern, uniform vs right-skewed.
- `F1`: strategy x table inventory.
- `F2`: queue type x arrival pattern.
- `F3`: ordering configuration x patience.
- `F4`: server count x patience.
- `F5`: reservation policy x table scarcity.
- `F6`: strategy x queue type.

## Outputs

- `inputs/baseline_casual_dining_seed42.json`: canonical v2 baseline.
- `inputs/shared_arrivals/`: shared queue inputs used to keep comparisons controlled.
- `outputs/`: result text files and executable scenario JSON files for every run and seed.
- `summaries/v2_all_runs_raw_metrics.csv`: per-run, per-seed metrics.
- `summaries/v2_pair_metric_summary.csv`: mean, min, max, and range per metric per run.
- `summaries/v2_assertions.csv`: assertion pass/fail results.
- `summaries/oat_decision_gate.csv`: OAT factor pass/fail table.
- `summaries/factorial_interactions.csv`: B-A, D-C, and interaction gaps.
- `insights/analysis_report.md`: paper-ready v2 summary.
