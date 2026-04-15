from __future__ import annotations

import random

from domain.business_model import BusinessModel
from domain.models import GroupArrival, Scenario


def _weighted_group_sizes(group_size_weights: dict[int, float]) -> tuple[list[int], list[float]]:
    sizes = sorted(group_size_weights)
    weights = [group_size_weights[size] for size in sizes]
    return sizes, weights


def generate_random_scenario(
    business_model: BusinessModel,
    seed: int,
    arrival_count: int,
    duration: int,
    generated: bool = True,
) -> Scenario:
    rng = random.Random(seed)
    sizes, weights = _weighted_group_sizes(business_model.generator_profile.group_size_weights)

    arrivals: list[GroupArrival] = []
    for index in range(arrival_count):
        arrival_time = rng.randint(0, duration)
        group_size = rng.choices(sizes, weights=weights, k=1)[0]
        dining_duration = rng.randint(
            business_model.generator_profile.min_dining_duration,
            business_model.generator_profile.max_dining_duration,
        )
        arrivals.append(
            GroupArrival(
                group_id=f"G{index + 1}",
                arrival_time=arrival_time,
                group_size=group_size,
                dining_duration=dining_duration,
            )
        )

    arrivals.sort(key=lambda arrival: (arrival.arrival_time, arrival.group_id))
    return Scenario(
        business_model_name=business_model.name,
        queue_type=business_model.queue_type,
        strategy_name=business_model.strategy_name,
        tables=business_model.tables,
        arrivals=arrivals,
        seed=seed,
        generated=generated,
    )
