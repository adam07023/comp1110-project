from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from generation.validators import QUEUE_TYPES, RESERVATION_POLICIES, STRATEGIES
from presets.builtins import get_builtin_models

TABLE_KEYS = {"seats", "count"}
ALLOWED_OVERRIDE_KEYS = {
    "queue_type",
    "strategy",
    "strategy_name",
    "arrival_pattern",
    "tables",
    "servers",
    "counters",
    "kiosks",
    "kiosk_usage_percent",
    "counter_order_time_min",
    "counter_order_time_max",
    "counter_order_time_mean",
    "counter_order_time_sd",
    "kiosk_order_time_min",
    "kiosk_order_time_max",
    "kiosk_order_time_mean",
    "kiosk_order_time_sd",
    "patience_threshold_mean",
    "patience_threshold_sd",
    "reservation_policy",
    "reserved_table_percent",
    "reservation_hold_before_min",
    "reservation_hold_after_min",
}
ALLOWED_DIRECTIONS = {"increase", "decrease", "no_change"}


@dataclass(frozen=True)
class AnalysisRunConfig:
    name: str
    parameter_overrides: dict[str, Any] = field(default_factory=dict)
    expected_metrics_direction: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisExperimentConfig:
    scenario_name: str
    base_model: str
    runs: list[AnalysisRunConfig]
    seeds: list[int] = field(default_factory=list)
    arrival_count: int | None = None
    duration: int | None = None
    baseline_overrides: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    reservation_every_n: int | None = None


@dataclass(frozen=True)
class AnalysisSuiteConfig:
    experiments: list[AnalysisExperimentConfig]
    default_seeds: list[int] = field(default_factory=lambda: [42, 101, 999])
    default_arrival_count: int = 40
    default_duration: int = 120
    output_title: str = "Automated Scenario Analysis"


def load_analysis_config(path: Path) -> AnalysisSuiteConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Analysis config must be a JSON object")
    suite = _parse_suite(payload)
    validate_analysis_config(suite)
    return suite


def validate_analysis_config(suite: AnalysisSuiteConfig) -> None:
    if not suite.experiments:
        raise ValueError("Analysis config must define at least one experiment")
    if not suite.default_seeds:
        raise ValueError("default_seeds must not be empty")
    if suite.default_arrival_count <= 0:
        raise ValueError("default_arrival_count must be positive")
    if suite.default_duration <= 0:
        raise ValueError("default_duration must be positive")

    seen_names: set[str] = set()
    builtins = get_builtin_models()
    for experiment in suite.experiments:
        if not experiment.scenario_name:
            raise ValueError("Experiment scenario_name must not be empty")
        if experiment.scenario_name in seen_names:
            raise ValueError(f"Duplicate experiment scenario_name: {experiment.scenario_name}")
        seen_names.add(experiment.scenario_name)
        if experiment.base_model not in builtins:
            raise ValueError(f"Unknown base_model: {experiment.base_model}")
        if not experiment.runs:
            raise ValueError(f"Experiment {experiment.scenario_name} must define at least one run")
        if experiment.arrival_count is not None and experiment.arrival_count <= 0:
            raise ValueError(f"Experiment {experiment.scenario_name} arrival_count must be positive")
        if experiment.duration is not None and experiment.duration <= 0:
            raise ValueError(f"Experiment {experiment.scenario_name} duration must be positive")
        if experiment.reservation_every_n is not None and experiment.reservation_every_n <= 0:
            raise ValueError(
                f"Experiment {experiment.scenario_name} reservation_every_n must be positive"
            )
        _validate_overrides(experiment.baseline_overrides, experiment.scenario_name)

        seen_runs: set[str] = set()
        for run in experiment.runs:
            if not run.name:
                raise ValueError(f"Experiment {experiment.scenario_name} has an empty run name")
            if run.name in seen_runs:
                raise ValueError(
                    f"Experiment {experiment.scenario_name} has duplicate run name: {run.name}"
                )
            seen_runs.add(run.name)
            _validate_overrides(run.parameter_overrides, f"{experiment.scenario_name}/{run.name}")
            for metric, direction in run.expected_metrics_direction.items():
                if not metric:
                    raise ValueError(f"Run {run.name} has an empty expected metric name")
                if direction not in ALLOWED_DIRECTIONS:
                    raise ValueError(
                        f"Run {run.name} has invalid expected direction {direction!r}"
                    )


def _parse_suite(payload: dict[str, Any]) -> AnalysisSuiteConfig:
    experiments_payload = payload.get("experiments")
    if not isinstance(experiments_payload, list):
        raise ValueError("Analysis config must include an experiments list")
    return AnalysisSuiteConfig(
        experiments=[_parse_experiment(row) for row in experiments_payload],
        default_seeds=[int(seed) for seed in payload.get("default_seeds", [42, 101, 999])],
        default_arrival_count=int(payload.get("default_arrival_count", 40)),
        default_duration=int(payload.get("default_duration", 120)),
        output_title=str(payload.get("output_title", "Automated Scenario Analysis")),
    )


def _parse_experiment(payload: Any) -> AnalysisExperimentConfig:
    if not isinstance(payload, dict):
        raise ValueError("Each experiment must be a JSON object")
    runs_payload = payload.get("runs")
    if not isinstance(runs_payload, list):
        raise ValueError("Each experiment must include a runs list")
    return AnalysisExperimentConfig(
        scenario_name=str(payload.get("scenario_name", "")),
        base_model=str(payload.get("base_model", "")),
        runs=[_parse_run(row) for row in runs_payload],
        seeds=[int(seed) for seed in payload.get("seeds", [])],
        arrival_count=(
            int(payload["arrival_count"]) if payload.get("arrival_count") is not None else None
        ),
        duration=int(payload["duration"]) if payload.get("duration") is not None else None,
        baseline_overrides=_dict_field(payload, "baseline_overrides"),
        description=str(payload.get("description", "")),
        reservation_every_n=(
            int(payload["reservation_every_n"])
            if payload.get("reservation_every_n") is not None
            else None
        ),
    )


def _parse_run(payload: Any) -> AnalysisRunConfig:
    if not isinstance(payload, dict):
        raise ValueError("Each run must be a JSON object")
    return AnalysisRunConfig(
        name=str(payload.get("name", "")),
        parameter_overrides=_dict_field(payload, "parameter_overrides"),
        expected_metrics_direction=_string_dict_field(payload, "expected_metrics_direction"),
    )


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return dict(value)


def _string_dict_field(payload: dict[str, Any], key: str) -> dict[str, str]:
    value = _dict_field(payload, key)
    return {str(metric): str(direction) for metric, direction in value.items()}


def _validate_overrides(overrides: dict[str, Any], label: str) -> None:
    unknown_keys = set(overrides) - ALLOWED_OVERRIDE_KEYS
    if unknown_keys:
        unknown = ", ".join(sorted(unknown_keys))
        raise ValueError(f"Unsupported override key(s) in {label}: {unknown}")
    if "queue_type" in overrides and overrides["queue_type"] not in QUEUE_TYPES:
        raise ValueError(f"Unknown queue_type in {label}: {overrides['queue_type']}")
    strategy = overrides.get("strategy", overrides.get("strategy_name"))
    if strategy is not None and strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy in {label}: {strategy}")
    if "reservation_policy" in overrides and overrides["reservation_policy"] not in RESERVATION_POLICIES:
        raise ValueError(f"Unknown reservation_policy in {label}: {overrides['reservation_policy']}")
    if "kiosk_usage_percent" in overrides:
        kiosk_usage_percent = float(overrides["kiosk_usage_percent"])
        if not 0.0 <= kiosk_usage_percent <= 1.0:
            raise ValueError(f"kiosk_usage_percent in {label} must be between 0.0 and 1.0")
    if "tables" in overrides:
        _validate_tables(overrides["tables"], label)


def _validate_tables(value: Any, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"tables override in {label} must be a non-empty list")
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"Each table row in {label} must be an object")
        if set(row) != TABLE_KEYS:
            raise ValueError(f"Each table row in {label} must contain seats and count")
        if int(row["seats"]) <= 0 or int(row["count"]) <= 0:
            raise ValueError(f"Table seats/count in {label} must be positive")
