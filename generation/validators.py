from __future__ import annotations

from domain.models import Scenario


def validate_scenario(scenario: Scenario) -> None:
    if not scenario.business_model_name:
        raise ValueError("Scenario must include a business model name")
    if not scenario.tables:
        raise ValueError("Scenario must define at least one table inventory row")

    for table in scenario.tables:
        if not isinstance(table.seats, int) or not isinstance(table.count, int):
            raise ValueError("Table seats and counts must be integers")
        if table.seats <= 0 or table.count <= 0:
            raise ValueError("Table seats and counts must be positive")

    seen_ids: set[str] = set()
    for arrival in scenario.arrivals:
        if arrival.group_id in seen_ids:
            raise ValueError(f"Duplicate group id: {arrival.group_id}")
        seen_ids.add(arrival.group_id)

        if not isinstance(arrival.arrival_time, int):
            raise ValueError(f"Arrival time must be an integer for {arrival.group_id}")
        if not isinstance(arrival.group_size, int):
            raise ValueError(f"Group size must be an integer for {arrival.group_id}")
        if not isinstance(arrival.dining_duration, int):
            raise ValueError(f"Dining duration must be an integer for {arrival.group_id}")
        if arrival.patience_override is not None and not isinstance(arrival.patience_override, int):
            raise ValueError(f"Patience override must be an integer for {arrival.group_id}")
        if arrival.arrival_time < 0:
            raise ValueError(f"Arrival time cannot be negative for {arrival.group_id}")
        if arrival.group_size <= 0:
            raise ValueError(f"Group size must be positive for {arrival.group_id}")
        if arrival.dining_duration <= 0:
            raise ValueError(f"Dining duration must be positive for {arrival.group_id}")
        if arrival.patience_override is not None and arrival.patience_override <= 0:
            raise ValueError(f"Patience override must be positive for {arrival.group_id}")

    if scenario.patience_threshold_mean <= 0:
        raise ValueError("Patience mean threshold must be positive")
    if scenario.patience_threshold_sd < 0:
        raise ValueError("Patience threshold standard deviation cannot be negative")
