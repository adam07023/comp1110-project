from __future__ import annotations

from domain.models import Scenario

QUEUE_TYPES = {"single_queue", "queue_by_group_size"}
STRATEGIES = {
    "fifo_fit",
    "best_fit",
    "smallest_table_fit",
    "strict_fifo_fit",
    "first_available",
    "exact_match",
}
ORDERING_TYPES = {"counter_only", "hybrid"}
RESERVATION_POLICIES = {"none", "hybrid_allocation"}


def validate_scenario(scenario: Scenario) -> None:
    if not scenario.business_model_name:
        raise ValueError("Scenario must include a business model name")
    if scenario.queue_type not in QUEUE_TYPES:
        raise ValueError(f"Unknown queue type: {scenario.queue_type}")
    if scenario.strategy_name not in STRATEGIES:
        raise ValueError(f"Unknown strategy name: {scenario.strategy_name}")
    if not scenario.tables:
        raise ValueError("Scenario must define at least one table inventory row")
    if scenario.ordering_type not in ORDERING_TYPES:
        raise ValueError(f"Unknown ordering type: {scenario.ordering_type}")
    if scenario.reservation_policy not in RESERVATION_POLICIES:
        raise ValueError(f"Unknown reservation policy: {scenario.reservation_policy}")
    if scenario.servers < 0:
        raise ValueError("Server count cannot be negative")
    if scenario.ordering_type == "counter_only" and scenario.servers <= 0:
        raise ValueError("Counter-only ordering requires at least one server")
    if scenario.kiosks < 0:
        raise ValueError("Kiosk count cannot be negative")
    if scenario.ordering_type == "hybrid" and scenario.servers + scenario.kiosks <= 0:
        raise ValueError("Hybrid ordering requires at least one server or kiosk")
    if not 0.0 <= scenario.kiosk_usage_percent <= 1.0:
        raise ValueError("Kiosk usage percent must be between 0.0 and 1.0")
    if scenario.reservation_policy == "none" and scenario.reserved_table_percent != 0.0:
        raise ValueError("Reserved table percent must be 0.0 when reservations are disabled")
    if not 0.0 <= scenario.reserved_table_percent <= 1.0:
        raise ValueError("Reserved table percent must be between 0.0 and 1.0")
    if scenario.reservation_hold_before_min < 0 or scenario.reservation_hold_after_min < 0:
        raise ValueError("Reservation hold windows cannot be negative")

    _validate_bounds(
        "Counter order time",
        scenario.counter_order_time_min,
        scenario.counter_order_time_max,
        scenario.counter_order_time_mean,
        scenario.counter_order_time_sd,
    )
    if scenario.ordering_type == "hybrid":
        _validate_bounds(
            "Kiosk order time",
            scenario.kiosk_order_time_min,
            scenario.kiosk_order_time_max,
            scenario.kiosk_order_time_mean,
            scenario.kiosk_order_time_sd,
        )

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
        if arrival.is_reservation and arrival.scheduled_time is None:
            raise ValueError(f"Reservation {arrival.group_id} must include a scheduled time")
        if arrival.scheduled_time is not None and arrival.scheduled_time < 0:
            raise ValueError(f"Scheduled time cannot be negative for {arrival.group_id}")

    if scenario.patience_threshold_mean <= 0:
        raise ValueError("Patience mean threshold must be positive")
    if scenario.patience_threshold_sd < 0:
        raise ValueError("Patience threshold standard deviation cannot be negative")


def _validate_bounds(label: str, minimum: int, maximum: int, mean: float, sd: float) -> None:
    if minimum < 0 or maximum < 0:
        raise ValueError(f"{label} bounds cannot be negative")
    if minimum > maximum:
        raise ValueError(f"{label} minimum cannot exceed maximum")
    if mean < 0:
        raise ValueError(f"{label} mean cannot be negative")
    if sd < 0:
        raise ValueError(f"{label} standard deviation cannot be negative")
    if minimum < maximum and not minimum <= mean <= maximum:
        raise ValueError(f"{label} mean must be within bounds")
