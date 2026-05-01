from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path

from domain.models import GroupArrival, Scenario, TableInventory
from generation.validators import validate_scenario


def _scenario_to_dict(scenario: Scenario) -> dict[str, object]:
    return {
        "business_model": {
            "name": scenario.business_model_name,
            "queue_type": scenario.queue_type,
            "strategy": scenario.strategy_name,
            "tables": [{"seats": table.seats, "count": table.count} for table in scenario.tables],
            "counters": scenario.counters,
            "kiosks": scenario.kiosks,
            "kiosk_usage_percent": scenario.kiosk_usage_percent,
            "counter_order_time_min": scenario.counter_order_time_min,
            "counter_order_time_max": scenario.counter_order_time_max,
            "counter_order_time_mean": scenario.counter_order_time_mean,
            "counter_order_time_sd": scenario.counter_order_time_sd,
            "kiosk_order_time_min": scenario.kiosk_order_time_min,
            "kiosk_order_time_max": scenario.kiosk_order_time_max,
            "kiosk_order_time_mean": scenario.kiosk_order_time_mean,
            "kiosk_order_time_sd": scenario.kiosk_order_time_sd,
            "reservation_policy": scenario.reservation_policy,
            "reserved_table_percent": scenario.reserved_table_percent,
            "reservation_hold_before_min": scenario.reservation_hold_before_min,
            "reservation_hold_after_min": scenario.reservation_hold_after_min,
            "patience_threshold_mean": scenario.patience_threshold_mean,
            "patience_threshold_sd": scenario.patience_threshold_sd,
        },
        "seed": scenario.seed,
        "generated": scenario.generated,
        "arrivals": [
            {
                "group_id": arrival.group_id,
                "arrival_time": arrival.arrival_time,
                "group_size": arrival.group_size,
                "dining_duration": arrival.dining_duration,
                "patience": arrival.patience_override,
                "is_reservation": arrival.is_reservation,
                "scheduled_time": arrival.scheduled_time,
            }
            for arrival in scenario.arrivals
        ],
    }


def write_scenario_json(path: Path, scenario: Scenario) -> None:
    validate_scenario(scenario)
    payload = _scenario_to_dict(scenario)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_scenario_json(path: Path) -> Scenario:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as error:
        raise ValueError(f"Invalid JSON syntax: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ValueError("Scenario JSON must be an object")
    business_model = payload.get("business_model")
    if isinstance(business_model, dict):
        model_payload = business_model
        tables_payload = model_payload.get("tables", [])
        business_model_name = str(model_payload["name"])
        queue_type = str(model_payload["queue_type"])
        strategy_name = str(model_payload["strategy"])
        patience_threshold_mean = float(model_payload.get("patience_threshold_mean", 45.0))
        patience_threshold_sd = float(model_payload.get("patience_threshold_sd", 10.0))
    else:
        model_payload = payload
        tables_payload = payload.get("tables", [])
        business_model_name = str(payload["business_model_name"])
        queue_type = str(payload["queue_type"])
        strategy_name = str(payload["strategy_name"])
        patience_threshold_mean = float(payload.get("patience_threshold_mean", 45.0))
        patience_threshold_sd = float(payload.get("patience_threshold_sd", 10.0))

    counters = int(model_payload.get("counters", model_payload.get("servers", 1)))
    kiosks = int(model_payload.get("kiosks", 0))
    default_kiosk_usage = kiosks / (counters + kiosks) if counters + kiosks > 0 else 0.0

    scenario = Scenario(
        business_model_name=business_model_name,
        queue_type=queue_type,
        strategy_name=strategy_name,
        tables=[
            TableInventory(seats=int(row["seats"]), count=int(row["count"]))
            for row in tables_payload
        ],
        arrivals=[
            GroupArrival(
                group_id=str(row.get("group_id", f"G{index + 1}")),
                arrival_time=int(row["arrival_time"]),
                group_size=int(row["group_size"]),
                dining_duration=int(row["dining_duration"]),
                patience_override=(
                    int(row["patience"])
                    if row.get("patience") is not None
                    else (
                        int(row["patience_override"])
                        if row.get("patience_override") is not None
                        else None
                    )
                ),
                is_reservation=bool(row.get("is_reservation", False)),
                scheduled_time=(
                    int(row["scheduled_time"]) if row.get("scheduled_time") is not None else None
                ),
            )
            for index, row in enumerate(payload.get("arrivals", []))
        ],
        patience_threshold_mean=patience_threshold_mean,
        patience_threshold_sd=patience_threshold_sd,
        seed=(int(payload["seed"]) if payload.get("seed") is not None else None),
        generated=bool(payload.get("generated", False)),
        counters=counters,
        kiosks=kiosks,
        kiosk_usage_percent=float(model_payload.get("kiosk_usage_percent", default_kiosk_usage)),
        counter_order_time_min=int(model_payload.get("counter_order_time_min", 0)),
        counter_order_time_max=int(model_payload.get("counter_order_time_max", 0)),
        counter_order_time_mean=float(model_payload.get("counter_order_time_mean", 0.0)),
        counter_order_time_sd=float(model_payload.get("counter_order_time_sd", 0.0)),
        kiosk_order_time_min=int(model_payload.get("kiosk_order_time_min", model_payload.get("counter_order_time_min", 0))),
        kiosk_order_time_max=int(model_payload.get("kiosk_order_time_max", model_payload.get("counter_order_time_max", 0))),
        kiosk_order_time_mean=float(model_payload.get("kiosk_order_time_mean", model_payload.get("counter_order_time_mean", 0.0))),
        kiosk_order_time_sd=float(model_payload.get("kiosk_order_time_sd", model_payload.get("counter_order_time_sd", 0.0))),
        reservation_policy=str(model_payload.get("reservation_policy", "none")),
        reserved_table_percent=float(model_payload.get("reserved_table_percent", 0.0)),
        reservation_hold_before_min=int(model_payload.get("reservation_hold_before_min", 0)),
        reservation_hold_after_min=int(model_payload.get("reservation_hold_after_min", 0)),
    )
    validate_scenario(scenario)
    return scenario
