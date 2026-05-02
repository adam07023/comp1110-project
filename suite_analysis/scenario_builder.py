from __future__ import annotations

from dataclasses import replace
from typing import Any

from suite_analysis.config import AnalysisExperimentConfig, AnalysisRunConfig
from domain.business_model import BusinessModel
from domain.models import GroupArrival, Scenario, TableInventory
from generation.randomizer import generate_random_scenario
from presets.builtins import get_builtin_models


def build_scenario(
    experiment: AnalysisExperimentConfig,
    run: AnalysisRunConfig,
    seed: int,
    default_arrival_count: int,
    default_duration: int,
) -> Scenario:
    base_model = _model_with_overrides(
        get_builtin_models()[experiment.base_model],
        experiment.baseline_overrides,
    )
    run_model = _model_with_overrides(base_model, run.parameter_overrides)
    arrival_model = _arrival_model(base_model, run_model, run.parameter_overrides)
    arrival_count = experiment.arrival_count or default_arrival_count
    duration = experiment.duration or default_duration

    base_arrivals = generate_random_scenario(
        arrival_model,
        seed=seed,
        arrival_count=arrival_count,
        duration=duration,
        generated=True,
    ).arrivals
    arrivals = _normalize_arrivals(base_arrivals, run_model, experiment.reservation_every_n)
    return Scenario(
        business_model_name=run_model.name,
        queue_type=run_model.queue_type,
        strategy_name=run_model.strategy_name,
        tables=run_model.tables,
        arrivals=arrivals,
        patience_threshold_mean=run_model.patience_threshold_mean,
        patience_threshold_sd=run_model.patience_threshold_sd,
        seed=seed,
        generated=True,
        counters=run_model.counters,
        kiosks=run_model.kiosks,
        kiosk_usage_percent=run_model.kiosk_usage_percent,
        counter_order_time_min=run_model.counter_order_time_min,
        counter_order_time_max=run_model.counter_order_time_max,
        counter_order_time_mean=run_model.counter_order_time_mean,
        counter_order_time_sd=run_model.counter_order_time_sd,
        kiosk_order_time_min=run_model.kiosk_order_time_min,
        kiosk_order_time_max=run_model.kiosk_order_time_max,
        kiosk_order_time_mean=run_model.kiosk_order_time_mean,
        kiosk_order_time_sd=run_model.kiosk_order_time_sd,
        reservation_policy=run_model.reservation_policy,
        reserved_table_percent=run_model.reserved_table_percent,
        reservation_hold_before_min=run_model.reservation_hold_before_min,
        reservation_hold_after_min=run_model.reservation_hold_after_min,
    )


def _arrival_model(
    base_model: BusinessModel,
    run_model: BusinessModel,
    run_overrides: dict[str, Any],
) -> BusinessModel:
    """Keep workloads shared except when arrival or patience is an experimental factor."""
    overrides: dict[str, Any] = {}
    if "arrival_pattern" in run_overrides:
        overrides["arrival_pattern"] = run_model.arrival_pattern
    if "patience_threshold_mean" in run_overrides or "patience_threshold_sd" in run_overrides:
        overrides["patience_threshold_mean"] = run_model.patience_threshold_mean
        overrides["patience_threshold_sd"] = run_model.patience_threshold_sd
    return replace(base_model, **overrides)


def _normalize_arrivals(
    arrivals: list[GroupArrival],
    model: BusinessModel,
    reservation_every_n: int | None,
) -> list[GroupArrival]:
    normalized: list[GroupArrival] = []
    for index, arrival in enumerate(arrivals, start=1):
        is_reservation = (
            model.reservation_policy == "hybrid_allocation"
            and reservation_every_n is not None
            and index % reservation_every_n == 0
        )
        # Stable IDs keep cross-run comparisons deterministic and readable.
        group_prefix = "R" if is_reservation else "G"
        normalized.append(
            GroupArrival(
                group_id=f"{group_prefix}{index}",
                arrival_time=arrival.arrival_time,
                group_size=arrival.group_size,
                dining_duration=arrival.dining_duration,
                patience_override=arrival.patience_override,
                is_reservation=is_reservation,
                scheduled_time=arrival.arrival_time if is_reservation else None,
            )
        )
    return sorted(normalized, key=lambda item: (item.arrival_time, item.group_id))


def _model_with_overrides(model: BusinessModel, overrides: dict[str, Any]) -> BusinessModel:
    normalized = dict(overrides)
    # Accept legacy/short config keys and normalize to dataclass field names.
    if "strategy" in normalized:
        normalized["strategy_name"] = normalized.pop("strategy")
    if "servers" in normalized and "counters" not in normalized:
        normalized["counters"] = normalized.pop("servers")
    if "tables" in normalized:
        normalized["tables"] = _parse_tables(normalized["tables"])
    return replace(model, **normalized)


def _parse_tables(rows: list[dict[str, object]]) -> list[TableInventory]:
    return [
        TableInventory(seats=int(row["seats"]), count=int(row["count"]))
        for row in rows
    ]
