from __future__ import annotations

import random
from dataclasses import dataclass

from domain.business_model import BusinessModel
from domain.models import GroupArrival

MAX_QUEUE_LENGTH = 99

ARRIVAL_COUNT_DISTRIBUTIONS: dict[str, tuple[float, float]] = {
    "fast_food": (26.0, 6.0),
    "fine_dining": (14.0, 4.0),
    "casual_dining": (34.0, 8.0),
    "cafe": (22.0, 5.0),
    "food_truck": (40.0, 10.0),
}


@dataclass(frozen=True)
class QueueRowInput:
    arrival_time: int
    group_size: int
    dining_duration: int
    patience_override: int | None = None


def sample_arrival_count(model_name: str, rng: random.Random) -> int:
    mean, sd = ARRIVAL_COUNT_DISTRIBUTIONS.get(model_name, (20.0, 6.0))
    sampled = int(round(rng.gauss(mean, sd)))
    return min(MAX_QUEUE_LENGTH, max(0, sampled))


def validate_queue_rows(rows: list[QueueRowInput], model: BusinessModel) -> list[GroupArrival]:
    if len(rows) > MAX_QUEUE_LENGTH:
        raise ValueError(f"Queue length cannot exceed {MAX_QUEUE_LENGTH}")

    profile = model.generator_profile
    seen_arrivals: set[int] = set()
    normalized: list[GroupArrival] = []

    for index, row in enumerate(rows, start=1):
        if row.arrival_time < 0:
            raise ValueError("Arrival time cannot be negative")
        if row.arrival_time in seen_arrivals:
            raise ValueError("Arrival times must be unique")
        seen_arrivals.add(row.arrival_time)

        if not (profile.min_group_size <= row.group_size <= profile.max_group_size):
            raise ValueError(
                f"Group size must be between {profile.min_group_size} and {profile.max_group_size}"
            )
        if not (profile.min_dining_duration <= row.dining_duration <= profile.max_dining_duration):
            raise ValueError(
                "Dining duration must be between "
                f"{profile.min_dining_duration} and {profile.max_dining_duration}"
            )
        if row.patience_override is not None and row.patience_override <= 0:
            raise ValueError("Patience value must be positive when provided")

        normalized.append(
            GroupArrival(
                group_id=f"G{index}",
                arrival_time=row.arrival_time,
                group_size=row.group_size,
                dining_duration=row.dining_duration,
                patience_override=row.patience_override,
            )
        )

    normalized.sort(key=lambda row: row.arrival_time)
    return normalized
