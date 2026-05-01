from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domain.business_model import BusinessModel  # noqa: E402
from domain.models import GroupArrival, Scenario, SimulationResult, TableInventory  # noqa: E402
from fileio.json_scenario_io import write_scenario_json  # noqa: E402
from fileio.result_writer import write_result_file  # noqa: E402
from generation.randomizer import generate_random_scenario  # noqa: E402
from presets.builtins import get_builtin_models  # noqa: E402
from simulation.allocator import expand_tables  # noqa: E402
from simulation.engine import run_simulation  # noqa: E402

SCENARIO_DIR = ROOT / "scenarios"
INPUT_DIR = ROOT / "inputs"
OUTPUT_DIR = ROOT / "outputs" / "v2"
SUMMARY_DIR = ROOT / "summaries"
INSIGHT_DIR = ROOT / "insights"

DEFAULT_SEEDS = [42, 123, 999]
DEFAULT_ARRIVAL_COUNT = {"casual_dining": 40, "fine_dining": 32}
DEFAULT_DURATION = {"casual_dining": 120, "fine_dining": 180}

BASELINE_OVERRIDES = {
    "casual_dining": {
        "queue_type": "single_queue",
        "strategy_name": "fifo_fit",
        "arrival_pattern": "centered",
        "tables": [
            TableInventory(seats=2, count=5),
            TableInventory(seats=4, count=6),
            TableInventory(seats=6, count=2),
        ],
        "counters": 3,
        "kiosks": 0,
        "kiosk_usage_percent": 0.0,
        "patience_threshold_mean": 24.0,
        "reservation_policy": "none",
        "reserved_table_percent": 0.0,
        "reservation_hold_before_min": 10,
        "reservation_hold_after_min": 10,
    },
    "fine_dining": {
        "queue_type": "queue_by_group_size",
        "strategy_name": "best_fit",
        "arrival_pattern": "right_skewed",
        "tables": [
            TableInventory(seats=2, count=5),
            TableInventory(seats=4, count=5),
            TableInventory(seats=6, count=3),
        ],
        "counters": 4,
        "kiosks": 0,
        "kiosk_usage_percent": 0.0,
        "patience_threshold_mean": 42.0,
        "reservation_hold_before_min": 10,
        "reservation_hold_after_min": 10,
    },
}

CORE_METRICS = [
    "average_wait_time",
    "min_wait_time",
    "max_wait_time",
    "average_ordering_wait_time",
    "service_level_rate",
    "table_utilization_rate",
    "server_utilization_rate",
    "served_groups",
    "rejected_groups",
    "abandoned_at_ordering",
    "abandoned_at_seating",
    "peak_ordering_queue_length",
    "peak_seating_queue_length",
    "longest_queue_length",
]


def main() -> int:
    configs = load_pair_configs(SCENARIO_DIR)
    for directory in (INPUT_DIR, OUTPUT_DIR, SUMMARY_DIR, INSIGHT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    baseline = build_baseline_scenario("casual_dining", 42)
    write_scenario_json(INPUT_DIR / "baseline_casual_dining_seed42.json", baseline)

    raw_rows: list[dict[str, object]] = []
    pair_summaries: list[dict[str, object]] = []
    assertion_rows: list[dict[str, object]] = []

    for config in configs:
        pair_rows = run_pair(config)
        raw_rows.extend(pair_rows)
        pair_summaries.extend(summarize_pair(config, pair_rows))
        assertion_rows.extend(evaluate_assertions(config, pair_rows))

    gate_rows = build_oat_gate(pair_summaries, raw_rows)
    interaction_rows = build_factorial_interactions(configs, pair_summaries)

    write_csv(SUMMARY_DIR / "v2_all_runs_raw_metrics.csv", raw_rows)
    write_csv(SUMMARY_DIR / "v2_pair_metric_summary.csv", pair_summaries)
    write_csv(SUMMARY_DIR / "v2_assertions.csv", assertion_rows)
    write_csv(SUMMARY_DIR / "oat_decision_gate.csv", gate_rows)
    write_csv(SUMMARY_DIR / "factorial_interactions.csv", interaction_rows)
    write_report(pair_summaries, assertion_rows, gate_rows, interaction_rows)
    print_assertions(assertion_rows)
    print(f"Executed {len(configs)} v2 scenario pairs.")
    print(f"Wrote outputs to {OUTPUT_DIR}")
    return 0


def load_pair_configs(path: Path) -> list[dict[str, Any]]:
    configs = []
    for target in sorted(path.glob("*.json")):
        payload = json.loads(target.read_text(encoding="utf-8"))
        validate_config(payload, target)
        configs.append(payload)
    if not configs:
        raise ValueError(f"No scenario configs found in {path}")
    return configs


def validate_config(config: dict[str, Any], path: Path) -> None:
    for key in ("pair_id", "description", "base_model", "runs"):
        if key not in config:
            raise ValueError(f"{path.name} missing required key: {key}")
    if config["base_model"] not in get_builtin_models():
        raise ValueError(f"{path.name} has unknown base_model {config['base_model']}")
    if not isinstance(config["runs"], list) or len(config["runs"]) < 2:
        raise ValueError(f"{path.name} must define at least two runs")
    seen = set()
    for run in config["runs"]:
        run_id = run.get("run_id")
        if not run_id or run_id in seen:
            raise ValueError(f"{path.name} has invalid or duplicate run_id")
        seen.add(run_id)
        if not isinstance(run.get("overrides", {}), dict):
            raise ValueError(f"{path.name}/{run_id} overrides must be an object")


def run_pair(config: dict[str, Any]) -> list[dict[str, object]]:
    rows = []
    seeds = [int(seed) for seed in config.get("seeds", DEFAULT_SEEDS)]
    for seed in seeds:
        for run in config["runs"]:
            scenario = build_run_scenario(config, run, seed)
            pair_dir = OUTPUT_DIR / config["pair_id"]
            pair_dir.mkdir(parents=True, exist_ok=True)
            result = run_simulation(scenario)
            output_path = pair_dir / f"{config['pair_id']}_{run['run_id']}_seed{seed}.txt"
            write_result_file(output_path, result)
            scenario_path = pair_dir / f"{config['pair_id']}_{run['run_id']}_seed{seed}.json"
            write_scenario_json(scenario_path, scenario)
            rows.append(
                {
                    "pair_id": config["pair_id"],
                    "kind": config.get("kind", ""),
                    "description": config["description"],
                    "run_id": run["run_id"],
                    "seed": seed,
                    "scenario_file": display_path(scenario_path),
                    "output_file": display_path(output_path),
                    **extract_metrics(result),
                }
            )
    return rows


def build_run_scenario(config: dict[str, Any], run: dict[str, Any], seed: int) -> Scenario:
    base_model = build_baseline_model(config["base_model"])
    overrides = normalize_overrides(run.get("overrides", {}))
    run_model = apply_overrides(base_model, overrides)
    arrival_model = arrival_source_model(base_model, run_model, overrides)
    arrival_count = int(config.get("arrival_count", DEFAULT_ARRIVAL_COUNT.get(config["base_model"], 40)))
    duration = int(config.get("duration", DEFAULT_DURATION.get(config["base_model"], 120)))
    generated = generate_random_scenario(arrival_model, seed, arrival_count, duration, generated=True)
    shared_path = shared_arrival_path(config["pair_id"], run["run_id"], seed, overrides)
    write_scenario_json(shared_path, scenario_from_model(arrival_model, generated.arrivals, seed))
    arrivals = normalize_arrivals(
        generated.arrivals,
        run_model,
        int(config.get("reservation_every_n", 0)) or None,
    )
    return scenario_from_model(run_model, arrivals, seed)


def shared_arrival_path(pair_id: str, run_id: str, seed: int, overrides: dict[str, Any]) -> Path:
    directory = INPUT_DIR / "shared_arrivals"
    directory.mkdir(parents=True, exist_ok=True)
    if (
        "arrival_pattern" in overrides
        or "patience_threshold_mean" in overrides
        or "patience_threshold_sd" in overrides
    ):
        return directory / f"{pair_id}_{run_id}_seed{seed}.json"
    return directory / f"{pair_id}_shared_seed{seed}.json"


def build_baseline_scenario(model_name: str, seed: int) -> Scenario:
    model = build_baseline_model(model_name)
    generated = generate_random_scenario(
        model,
        seed=seed,
        arrival_count=DEFAULT_ARRIVAL_COUNT.get(model_name, 40),
        duration=DEFAULT_DURATION.get(model_name, 120),
        generated=True,
    )
    return scenario_from_model(model, generated.arrivals, seed)


def build_baseline_model(model_name: str) -> BusinessModel:
    return replace(get_builtin_models()[model_name], **BASELINE_OVERRIDES.get(model_name, {}))


def normalize_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(overrides)
    if "strategy" in normalized:
        normalized["strategy_name"] = normalized.pop("strategy")
    if "servers" in normalized:
        normalized["counters"] = normalized.pop("servers")
    if "patience_mean" in normalized:
        normalized["patience_threshold_mean"] = normalized.pop("patience_mean")
    ordering_type = normalized.pop("ordering_type", None)
    if ordering_type == "counter_only":
        normalized["kiosks"] = 0
        normalized["kiosk_usage_percent"] = 0.0
    elif ordering_type == "hybrid":
        normalized.setdefault("kiosks", 3)
        normalized.setdefault("kiosk_usage_percent", 0.75)
    if "tables" in normalized:
        normalized["tables"] = [
            TableInventory(seats=int(row["seats"]), count=int(row["count"]))
            for row in normalized["tables"]
        ]
    return normalized


def apply_overrides(model: BusinessModel, overrides: dict[str, Any]) -> BusinessModel:
    return replace(model, **overrides)


def arrival_source_model(
    base_model: BusinessModel,
    run_model: BusinessModel,
    overrides: dict[str, Any],
) -> BusinessModel:
    arrival_overrides: dict[str, Any] = {}
    if "arrival_pattern" in overrides:
        arrival_overrides["arrival_pattern"] = run_model.arrival_pattern
    if "patience_threshold_mean" in overrides or "patience_threshold_sd" in overrides:
        arrival_overrides["patience_threshold_mean"] = run_model.patience_threshold_mean
        arrival_overrides["patience_threshold_sd"] = run_model.patience_threshold_sd
    return replace(base_model, **arrival_overrides)


def normalize_arrivals(
    arrivals: list[GroupArrival],
    model: BusinessModel,
    reservation_every_n: int | None,
) -> list[GroupArrival]:
    normalized = []
    for index, arrival in enumerate(arrivals, start=1):
        is_reservation = (
            model.reservation_policy == "hybrid_allocation"
            and reservation_every_n is not None
            and index % reservation_every_n == 0
        )
        normalized.append(
            GroupArrival(
                group_id=("R" if is_reservation else "G") + str(index),
                arrival_time=arrival.arrival_time,
                group_size=arrival.group_size,
                dining_duration=arrival.dining_duration,
                patience_override=arrival.patience_override,
                is_reservation=is_reservation,
                scheduled_time=arrival.arrival_time if is_reservation else None,
            )
        )
    return sorted(normalized, key=lambda item: (item.arrival_time, item.group_id))


def scenario_from_model(model: BusinessModel, arrivals: list[GroupArrival], seed: int) -> Scenario:
    return Scenario(
        business_model_name=model.name,
        queue_type=model.queue_type,
        strategy_name=model.strategy_name,
        tables=model.tables,
        arrivals=arrivals,
        patience_threshold_mean=model.patience_threshold_mean,
        patience_threshold_sd=model.patience_threshold_sd,
        seed=seed,
        generated=True,
        counters=model.counters,
        kiosks=model.kiosks,
        kiosk_usage_percent=model.kiosk_usage_percent,
        counter_order_time_min=model.counter_order_time_min,
        counter_order_time_max=model.counter_order_time_max,
        counter_order_time_mean=model.counter_order_time_mean,
        counter_order_time_sd=model.counter_order_time_sd,
        kiosk_order_time_min=model.kiosk_order_time_min,
        kiosk_order_time_max=model.kiosk_order_time_max,
        kiosk_order_time_mean=model.kiosk_order_time_mean,
        kiosk_order_time_sd=model.kiosk_order_time_sd,
        reservation_policy=model.reservation_policy,
        reserved_table_percent=model.reserved_table_percent,
        reservation_hold_before_min=model.reservation_hold_before_min,
        reservation_hold_after_min=model.reservation_hold_after_min,
    )


def extract_metrics(result: SimulationResult) -> dict[str, float]:
    stats = result.statistics
    metrics: dict[str, float] = {
        "average_wait_time": stats.average_wait_time,
        "min_wait_time": float(stats.min_wait_time or 0),
        "max_wait_time": float(stats.max_wait_time or 0),
        "average_ordering_wait_time": stats.average_ordering_wait_time,
        "service_level_rate": stats.service_level_rate,
        "table_utilization_rate": stats.table_utilization_rate,
        "server_utilization_rate": stats.server_utilization_rate,
        "served_groups": float(stats.served_groups),
        "rejected_groups": float(stats.rejected_groups),
        "abandoned_at_ordering": float(stats.abandoned_at_ordering),
        "abandoned_at_seating": float(stats.abandoned_at_seating),
        "reservation_groups_served": float(stats.reservation_groups_served),
        "reservation_no_shows": float(stats.reservation_no_shows),
        "reservation_tables_released": float(stats.reservation_tables_released),
        "longest_queue_length": float(stats.longest_queue_length),
        "peak_ordering_queue_length": float(peak_ordering_queue_length(result)),
        "peak_seating_queue_length": float(peak_seating_queue_length(result)),
    }
    for label, value in stats.max_queue_length_by_queue.items():
        safe_label = label.replace("+", "plus").replace("-", "_")
        metrics[f"max_queue_length_queue_{safe_label}"] = float(value)
    for table_size, value in table_utilization_by_size(result).items():
        metrics[f"table_utilization_size_{table_size}"] = value
    return metrics


def peak_ordering_queue_length(result: SimulationResult) -> int:
    intervals = []
    abandonment_times = abandonment_time_by_group(result)
    for seated in result.seated_groups:
        if seated.order_start_time is not None and seated.order_start_time > seated.group.arrival_time:
            intervals.append((seated.group.arrival_time, seated.order_start_time))
    for rejected in result.rejected:
        if rejected.stage == "ordering":
            end_time = abandonment_times.get(rejected.group.group_id)
            if end_time is not None and end_time > rejected.group.arrival_time:
                intervals.append((rejected.group.arrival_time, end_time))
    return peak_interval_count(intervals)


def peak_seating_queue_length(result: SimulationResult) -> int:
    intervals = []
    abandonment_times = abandonment_time_by_group(result)
    for seated in result.seated_groups:
        if (
            seated.seating_queue_enter_time is not None
            and seated.seated_time > seated.seating_queue_enter_time
        ):
            intervals.append((seated.seating_queue_enter_time, seated.seated_time))
    for rejected in result.rejected:
        if rejected.stage == "seating":
            enter_time = seating_enter_time(result, rejected.group.group_id)
            end_time = abandonment_times.get(rejected.group.group_id)
            if enter_time is not None and end_time is not None and end_time > enter_time:
                intervals.append((enter_time, end_time))
    return peak_interval_count(intervals)


def peak_interval_count(intervals: list[tuple[int, int]]) -> int:
    changes = []
    for start, end in intervals:
        changes.append((start, 1))
        changes.append((end, -1))
    current = 0
    peak = 0
    for _, delta in sorted(changes, key=lambda item: (item[0], item[1])):
        current += delta
        peak = max(peak, current)
    return peak


def abandonment_time_by_group(result: SimulationResult) -> dict[str, int]:
    return {
        event.group_id: event.timestamp
        for event in result.events
        if event.event_type == "abandonment" and event.group_id is not None
    }


def seating_enter_time(result: SimulationResult, group_id: str) -> int | None:
    for event in result.events:
        if event.group_id == group_id and event.event_type == "order_complete":
            return event.timestamp
    return None


def table_utilization_by_size(result: SimulationResult) -> dict[int, float]:
    tables = {table.table_id: table for table in expand_tables(result.scenario.tables)}
    table_counts: dict[int, int] = {}
    occupied_by_size: dict[int, int] = {}
    for table in tables.values():
        table_counts[table.seats] = table_counts.get(table.seats, 0) + 1
    for seated in result.seated_groups:
        table_size = tables[seated.table_id].seats
        occupied_by_size[table_size] = occupied_by_size.get(table_size, 0) + (
            seated.departure_time - seated.seated_time
        )
    if result.statistics.simulation_end_time <= 0:
        return {table_size: 0.0 for table_size in table_counts}
    return {
        table_size: occupied_by_size.get(table_size, 0)
        / (result.statistics.simulation_end_time * count)
        for table_size, count in table_counts.items()
    }


def summarize_pair(config: dict[str, Any], rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries = []
    for run in config["runs"]:
        run_rows = [row for row in rows if row["run_id"] == run["run_id"]]
        metric_names = sorted(
            key for row in run_rows for key, value in row.items() if isinstance(value, float)
        )
        summary: dict[str, object] = {
            "pair_id": config["pair_id"],
            "kind": config.get("kind", ""),
            "description": config["description"],
            "run_id": run["run_id"],
            "seed_count": len(run_rows),
        }
        for metric in sorted(set(metric_names)):
            values = [float(row[metric]) for row in run_rows if metric in row]
            summary[f"{metric}_mean"] = mean(values)
            summary[f"{metric}_min"] = min(values)
            summary[f"{metric}_max"] = max(values)
            summary[f"{metric}_range"] = max(values) - min(values)
        summaries.append(summary)
    return summaries


def evaluate_assertions(config: dict[str, Any], rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries = summarize_pair(config, rows)
    by_run = {row["run_id"]: row for row in summaries}
    assertion_rows = []
    for assertion in config.get("assertions", []):
        metric = assertion["metric"]
        left, operator, right = assertion["direction"].split()
        left_value = float(by_run[left][f"{metric}_mean"])
        right_value = float(by_run[right][f"{metric}_mean"])
        passed = left_value < right_value if operator == "<" else left_value > right_value
        assertion_rows.append(
            {
                "pair_id": config["pair_id"],
                "metric": metric,
                "direction": assertion["direction"],
                "left_value": left_value,
                "right_value": right_value,
                "passed": passed,
            }
        )
    return assertion_rows


def build_oat_gate(
    summaries: list[dict[str, object]],
    raw_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    gate_rows = []
    for pair_id in sorted({str(row["pair_id"]) for row in summaries if str(row["pair_id"]).startswith("S")}):
        pair_raw = [row for row in raw_rows if row["pair_id"] == pair_id]
        run_ids = sorted({str(row["run_id"]) for row in pair_raw})
        if len(run_ids) < 2:
            continue
        passing_metric = ""
        passing_mean_change = 0.0
        passing_sd = 0.0
        for metric in CORE_METRICS:
            diffs = paired_seed_differences(pair_raw, run_ids[0], run_ids[1], metric)
            if len(diffs) < 2:
                continue
            avg = mean(diffs)
            sd = stdev(diffs) if len(set(diffs)) > 1 else 0.0
            if abs(avg) > sd:
                passing_metric = metric
                passing_mean_change = avg
                passing_sd = sd
                break
        gate_rows.append(
            {
                "pair_id": pair_id,
                "factor_passes_gate": bool(passing_metric),
                "passing_metric": passing_metric,
                "mean_change": passing_mean_change,
                "sd_of_change": passing_sd,
            }
        )
    return gate_rows


def paired_seed_differences(
    rows: list[dict[str, object]],
    run_a: str,
    run_b: str,
    metric: str,
) -> list[float]:
    by_seed_run = {(row["seed"], row["run_id"]): row for row in rows}
    diffs = []
    for seed, run_id in sorted(by_seed_run):
        if run_id != run_a:
            continue
        a = by_seed_run.get((seed, run_a))
        b = by_seed_run.get((seed, run_b))
        if a is not None and b is not None and metric in a and metric in b:
            diffs.append(float(b[metric]) - float(a[metric]))
    return diffs


def build_factorial_interactions(
    configs: list[dict[str, Any]],
    summaries: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows = []
    by_pair_run = {(row["pair_id"], row["run_id"]): row for row in summaries}
    for config in configs:
        if not str(config["pair_id"]).startswith("F"):
            continue
        metric = config.get("interaction_metric", "average_wait_time")
        try:
            a = float(by_pair_run[(config["pair_id"], "A")][f"{metric}_mean"])
            b = float(by_pair_run[(config["pair_id"], "B")][f"{metric}_mean"])
            c = float(by_pair_run[(config["pair_id"], "C")][f"{metric}_mean"])
            d = float(by_pair_run[(config["pair_id"], "D")][f"{metric}_mean"])
        except KeyError:
            continue
        first_gap = b - a
        second_gap = d - c
        interaction = first_gap - second_gap
        rows.append(
            {
                "pair_id": config["pair_id"],
                "metric": metric,
                "b_minus_a": first_gap,
                "d_minus_c": second_gap,
                "interaction_gap": interaction,
                "interaction_detected": not math.isclose(interaction, 0.0, abs_tol=1e-9),
                "interpretation": interaction_interpretation(config["pair_id"], interaction),
            }
        )
    return rows


def interaction_interpretation(pair_id: str, interaction: float) -> str:
    if math.isclose(interaction, 0.0, abs_tol=1e-9):
        return "No measurable interaction in the selected metric."
    return f"The factor effect changes across levels for {pair_id}; inspect the sign relative to the metric."


def write_report(
    summaries: list[dict[str, object]],
    assertions: list[dict[str, object]],
    gate_rows: list[dict[str, object]],
    interaction_rows: list[dict[str, object]],
) -> None:
    lines = [
        "# Scenario Analysis V2 Report",
        "",
        "This report follows `scenario_analysis_spec_v2.md` and is generated by `Scenario analysis/runner.py`.",
        "",
        "## OAT Decision Gate",
        "",
        "| Pair | Passes | Passing metric | Mean change | SD of change |",
        "|---|---:|---|---:|---:|",
    ]
    for row in gate_rows:
        lines.append(
            f"| {row['pair_id']} | {row['factor_passes_gate']} | {row['passing_metric']} | "
            f"{float(row['mean_change']):.3f} | {float(row['sd_of_change']):.3f} |"
        )
    lines.extend(["", "## Factorial Interactions", "", "| Pair | Metric | B-A | D-C | Interaction | Detected |", "|---|---|---:|---:|---:|---:|"])
    for row in interaction_rows:
        lines.append(
            f"| {row['pair_id']} | {row['metric']} | {float(row['b_minus_a']):.3f} | "
            f"{float(row['d_minus_c']):.3f} | {float(row['interaction_gap']):.3f} | "
            f"{row['interaction_detected']} |"
        )
    lines.extend(["", "## Assertion Results", "", "| Pair | Metric | Direction | Passed |", "|---|---|---|---:|"])
    for row in assertions:
        lines.append(f"| {row['pair_id']} | {row['metric']} | {row['direction']} | {row['passed']} |")
    lines.extend(["", "## Pair Summary", ""])
    for pair_id in sorted({str(row["pair_id"]) for row in summaries}):
        pair_rows = [row for row in summaries if row["pair_id"] == pair_id]
        lines.extend([
            f"### {pair_id}",
            "",
            "| Run | Served mean | Avg wait mean | Avg wait range | Service level mean | Table util mean |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for row in pair_rows:
            lines.append(
                f"| {row['run_id']} | {float(row.get('served_groups_mean', 0)):.2f} | "
                f"{float(row.get('average_wait_time_mean', 0)):.2f} | "
                f"{float(row.get('average_wait_time_range', 0)):.2f} | "
                f"{float(row.get('service_level_rate_mean', 0)):.3f} | "
                f"{float(row.get('table_utilization_rate_mean', 0)):.3f} |"
            )
        lines.append("")
    (INSIGHT_DIR / "analysis_report.md").write_text("\n".join(lines), encoding="utf-8")


def print_assertions(rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    print("Assertion results:")
    for row in rows:
        status = "PASS" if row["passed"] else "FAIL"
        print(f"  {row['pair_id']} {row['metric']} {row['direction']}: {status}")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
