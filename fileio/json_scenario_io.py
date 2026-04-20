from __future__ import annotations

import json
from pathlib import Path

from domain.models import GroupArrival, Scenario, TableInventory
from generation.validators import validate_scenario


def _scenario_to_dict(scenario: Scenario) -> dict[str, object]:
    return {
        "business_model_name": scenario.business_model_name,
        "queue_type": scenario.queue_type,
        "strategy_name": scenario.strategy_name,
        "patience_threshold_mean": scenario.patience_threshold_mean,
        "patience_threshold_sd": scenario.patience_threshold_sd,
        "seed": scenario.seed,
        "generated": scenario.generated,
        "tables": [{"seats": table.seats, "count": table.count} for table in scenario.tables],
        "arrivals": [
            {
                "group_id": arrival.group_id,
                "arrival_time": arrival.arrival_time,
                "group_size": arrival.group_size,
                "dining_duration": arrival.dining_duration,
                "patience_override": arrival.patience_override,
            }
            for arrival in scenario.arrivals
        ],
    }


def write_scenario_json(path: Path, scenario: Scenario) -> None:
    validate_scenario(scenario)
    payload = _scenario_to_dict(scenario)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_scenario_json(path: Path) -> Scenario:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenario = Scenario(
        business_model_name=str(payload["business_model_name"]),
        queue_type=str(payload["queue_type"]),
        strategy_name=str(payload["strategy_name"]),
        tables=[
            TableInventory(seats=int(row["seats"]), count=int(row["count"]))
            for row in payload.get("tables", [])
        ],
        arrivals=[
            GroupArrival(
                group_id=str(row.get("group_id", f"G{index + 1}")),
                arrival_time=int(row["arrival_time"]),
                group_size=int(row["group_size"]),
                dining_duration=int(row["dining_duration"]),
                patience_override=(
                    int(row["patience_override"]) if row.get("patience_override") is not None else None
                ),
            )
            for index, row in enumerate(payload.get("arrivals", []))
        ],
        patience_threshold_mean=float(payload.get("patience_threshold_mean", 45.0)),
        patience_threshold_sd=float(payload.get("patience_threshold_sd", 10.0)),
        seed=(int(payload["seed"]) if payload.get("seed") is not None else None),
        generated=bool(payload.get("generated", False)),
    )
    validate_scenario(scenario)
    return scenario
