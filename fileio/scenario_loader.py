from __future__ import annotations

from pathlib import Path

from domain.models import GroupArrival, Scenario, TableInventory
from generation.validators import validate_scenario
from presets.builtins import get_builtin_models


def _read_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip().lower()
            sections[current_section] = []
            continue
        if current_section is None:
            raise ValueError("Content found before any section header")
        sections[current_section].append(line)

    return sections


def _parse_key_value_lines(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        if line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Expected key=value line, got: {line}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _parse_tables(lines: list[str]) -> list[TableInventory]:
    tables: list[TableInventory] = []
    for line in lines:
        if line.startswith("#"):
            continue
        seats_text, count_text = [part.strip() for part in line.split(",", 1)]
        tables.append(TableInventory(seats=int(seats_text), count=int(count_text)))
    return tables


def _parse_arrivals(lines: list[str]) -> list[GroupArrival]:
    arrivals: list[GroupArrival] = []
    next_group_number = 1
    for line in lines:
        if line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            group_id = f"G{next_group_number}"
            arrival_time_text, group_size_text, dining_duration_text = parts
            patience_override = None
        elif len(parts) == 4:
            group_id = f"G{next_group_number}"
            arrival_time_text, group_size_text, dining_duration_text, patience_text = parts
            patience_override = int(patience_text) if patience_text else None
        elif len(parts) == 5:
            group_id, arrival_time_text, group_size_text, dining_duration_text, patience_text = parts
            if not group_id:
                raise ValueError("Arrival group_id cannot be empty")
            patience_override = int(patience_text) if patience_text else None
        else:
            raise ValueError(
                "Arrival rows must contain either 3, 4, or 5 comma-separated values"
            )
        arrivals.append(
            GroupArrival(
                group_id=group_id,
                arrival_time=int(arrival_time_text),
                group_size=int(group_size_text),
                dining_duration=int(dining_duration_text),
                patience_override=patience_override,
            )
        )
        next_group_number += 1
    return arrivals


def load_scenario(path: Path) -> Scenario:
    sections = _read_sections(path)
    business_model = _parse_key_value_lines(sections.get("business_model", []))
    queue = _parse_key_value_lines(sections.get("queue", []))
    patience = _parse_key_value_lines(sections.get("patience", []))
    seed = _parse_key_value_lines(sections.get("seed", []))
    if "name" not in business_model:
        raise ValueError("Scenario must define business_model name")
    if "type" not in queue:
        raise ValueError("Scenario must define queue type")
    if "strategy" not in queue:
        raise ValueError("Scenario must define queue strategy")

    builtin_model = get_builtin_models().get(business_model["name"])

    mean_threshold = (
        float(patience["mean_threshold"])
        if patience.get("mean_threshold")
        else (builtin_model.patience_threshold_mean if builtin_model else 45.0)
    )
    sd_threshold = (
        float(patience["sd_threshold"])
        if patience.get("sd_threshold")
        else (builtin_model.patience_threshold_sd if builtin_model else 10.0)
    )

    scenario = Scenario(
        business_model_name=business_model["name"],
        queue_type=queue["type"],
        strategy_name=queue["strategy"],
        tables=_parse_tables(sections.get("tables", [])),
        arrivals=_parse_arrivals(sections.get("arrivals", [])),
        patience_threshold_mean=mean_threshold,
        patience_threshold_sd=sd_threshold,
        seed=int(seed["value"]) if seed.get("value") else None,
        generated=seed.get("generated", "false").lower() == "true",
    )
    validate_scenario(scenario)
    return scenario
