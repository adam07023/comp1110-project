from __future__ import annotations

from pathlib import Path

from domain.models import GroupArrival, Scenario, TableInventory
from generation.validators import validate_scenario


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
        arrival_time_text, group_size_text, dining_duration_text = [
            part.strip() for part in line.split(",", 2)
        ]
        arrivals.append(
            GroupArrival(
                group_id=f"G{next_group_number}",
                arrival_time=int(arrival_time_text),
                group_size=int(group_size_text),
                dining_duration=int(dining_duration_text),
            )
        )
        next_group_number += 1
    return arrivals


def load_scenario(path: Path) -> Scenario:
    sections = _read_sections(path)
    business_model = _parse_key_value_lines(sections.get("business_model", []))
    queue = _parse_key_value_lines(sections.get("queue", []))
    seed = _parse_key_value_lines(sections.get("seed", []))

    scenario = Scenario(
        business_model_name=business_model["name"],
        queue_type=queue["type"],
        strategy_name=queue["strategy"],
        tables=_parse_tables(sections.get("tables", [])),
        arrivals=_parse_arrivals(sections.get("arrivals", [])),
        seed=int(seed["value"]) if seed.get("value") else None,
        generated=seed.get("generated", "false").lower() == "true",
    )
    validate_scenario(scenario)
    return scenario
