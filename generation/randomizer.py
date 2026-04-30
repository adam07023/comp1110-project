from __future__ import annotations

import random

from domain.business_model import BusinessModel
from domain.models import GroupArrival, Scenario

try:
    from scipy.stats import truncnorm
except ModuleNotFoundError:  # pragma: no cover - exercised only when scipy is absent.
    truncnorm = None


def _weighted_group_sizes(group_size_weights: dict[int, float]) -> tuple[list[int], list[float]]:
    sizes = sorted(group_size_weights)
    weights = [group_size_weights[size] for size in sizes]
    return sizes, weights


def _sample_patience_override(business_model: BusinessModel, rng: random.Random) -> int:
    minimum, maximum = _patience_bounds(
        business_model.patience_threshold_mean,
        business_model.patience_threshold_sd,
    )
    return _sample_truncated_normal(
        minimum=minimum,
        maximum=maximum,
        mean=business_model.patience_threshold_mean,
        sd=business_model.patience_threshold_sd,
        rng=rng,
    )


def _patience_bounds(mean: float, sd: float) -> tuple[int, int]:
    spread = max(1.0, 2.0 * sd)
    minimum = max(1, int(round(mean - spread)))
    maximum = max(minimum, int(round(mean + spread)))
    return minimum, maximum


def _sample_truncated_normal(
    minimum: int,
    maximum: int,
    mean: float,
    sd: float,
    rng: random.Random,
) -> int:
    if minimum == maximum or sd == 0:
        return int(round(min(max(mean, minimum), maximum)))

    if truncnorm is not None:
        a = (minimum - mean) / sd
        b = (maximum - mean) / sd
        sampled = truncnorm.ppf(rng.random(), a, b, loc=mean, scale=sd)
        return min(maximum, max(minimum, int(round(sampled))))

    while True:
        sampled = int(round(rng.gauss(mean, sd)))
        if minimum <= sampled <= maximum:
            return sampled


def _sample_dining_duration(business_model: BusinessModel, rng: random.Random) -> int:
    profile = business_model.generator_profile
    min_duration = profile.min_dining_duration
    max_duration = profile.max_dining_duration

    if business_model.name == "food_truck":
        return rng.randint(min_duration, max_duration)

    mean = profile.dining_duration_mean
    sd = profile.dining_duration_sd
    if mean is None:
        mean = (min_duration + max_duration) / 2
    if sd is None:
        sd = max(1.0, (max_duration - min_duration) / 6)

    return _sample_truncated_normal(min_duration, max_duration, mean, sd, rng)


def _sample_arrival_time(business_model: BusinessModel, duration: int, rng: random.Random) -> int:
    if duration <= 0:
        return 0

    pattern = business_model.arrival_pattern
    if pattern == "uniform":
        # No positional bias. Every point in the window is equally likely.
        ratio = rng.random()
    elif pattern == "left_skewed":
        # Arrivals concentrate toward the start of the window and thin toward the end.
        ratio = rng.betavariate(2.0, 5.0)
    elif pattern == "centered":
        # Arrivals concentrate around the midpoint with tapering at both edges.
        ratio = rng.betavariate(3.0, 3.0)
    elif pattern == "right_skewed":
        # Arrivals concentrate toward the later portion of the window.
        ratio = rng.betavariate(5.0, 2.0)
    else:
        ratio = rng.random()

    bounded_ratio = min(1.0, max(0.0, ratio))
    return int(round(bounded_ratio * duration))


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
        arrival_time = _sample_arrival_time(business_model, duration, rng)
        group_size = rng.choices(sizes, weights=weights, k=1)[0]
        dining_duration = _sample_dining_duration(business_model, rng)
        arrivals.append(
            GroupArrival(
                group_id=f"G{index + 1}",
                arrival_time=arrival_time,
                group_size=group_size,
                dining_duration=dining_duration,
                patience_override=_sample_patience_override(business_model, rng),
            )
        )

    arrivals.sort(key=lambda arrival: (arrival.arrival_time, arrival.group_id))
    return Scenario(
        business_model_name=business_model.name,
        queue_type=business_model.queue_type,
        strategy_name=business_model.strategy_name,
        tables=business_model.tables,
        arrivals=arrivals,
        patience_threshold_mean=business_model.patience_threshold_mean,
        patience_threshold_sd=business_model.patience_threshold_sd,
        seed=seed,
        generated=generated,
        servers=business_model.servers,
        counter_order_time_min=business_model.counter_order_time_min,
        counter_order_time_max=business_model.counter_order_time_max,
        counter_order_time_mean=business_model.counter_order_time_mean,
        counter_order_time_sd=business_model.counter_order_time_sd,
        reservation_policy=business_model.reservation_policy,
        reserved_table_percent=business_model.reserved_table_percent,
        reservation_hold_before_min=business_model.reservation_hold_before_min,
        reservation_hold_after_min=business_model.reservation_hold_after_min,
    )
