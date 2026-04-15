from __future__ import annotations

from domain.business_model import BusinessModel, GeneratorProfile
from domain.models import TableInventory


def get_builtin_models() -> dict[str, BusinessModel]:
    return {
        "fast_food": BusinessModel(
            name="fast_food",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=4), TableInventory(seats=4, count=8)],
            generator_profile=GeneratorProfile(
                min_group_size=1,
                max_group_size=4,
                group_size_weights={1: 0.35, 2: 0.35, 3: 0.2, 4: 0.1},
                min_dining_duration=15,
                max_dining_duration=35,
            ),
            notes="Quick turnover with mostly small groups.",
        ),
        "fine_dining": BusinessModel(
            name="fine_dining",
            queue_type="queue_by_group_size",
            strategy_name="best_fit",
            tables=[TableInventory(seats=2, count=3), TableInventory(seats=4, count=6), TableInventory(seats=6, count=3)],
            generator_profile=GeneratorProfile(
                min_group_size=2,
                max_group_size=6,
                group_size_weights={2: 0.2, 3: 0.18, 4: 0.32, 5: 0.18, 6: 0.12},
                min_dining_duration=75,
                max_dining_duration=150,
            ),
            notes="Longer stays with more careful seat matching.",
        ),
        "casual_dining": BusinessModel(
            name="casual_dining",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=4), TableInventory(seats=4, count=7), TableInventory(seats=6, count=2)],
            generator_profile=GeneratorProfile(
                min_group_size=1,
                max_group_size=6,
                group_size_weights={1: 0.12, 2: 0.28, 3: 0.18, 4: 0.26, 5: 0.1, 6: 0.06},
                min_dining_duration=40,
                max_dining_duration=90,
            ),
            notes="Balanced turnover with family-sized groups.",
        ),
        "cafe": BusinessModel(
            name="cafe",
            queue_type="single_queue",
            strategy_name="smallest_table_fit",
            tables=[TableInventory(seats=1, count=4), TableInventory(seats=2, count=6), TableInventory(seats=4, count=3)],
            generator_profile=GeneratorProfile(
                min_group_size=1,
                max_group_size=4,
                group_size_weights={1: 0.42, 2: 0.34, 3: 0.14, 4: 0.1},
                min_dining_duration=25,
                max_dining_duration=60,
            ),
            notes="Small groups dominate and compact seating is favored.",
        ),
        "food_truck": BusinessModel(
            name="food_truck",
            queue_type="single_queue",
            strategy_name="strict_fifo_fit",
            tables=[TableInventory(seats=2, count=2), TableInventory(seats=4, count=2)],
            generator_profile=GeneratorProfile(
                min_group_size=1,
                max_group_size=4,
                group_size_weights={1: 0.4, 2: 0.32, 3: 0.16, 4: 0.12},
                min_dining_duration=10,
                max_dining_duration=25,
            ),
            notes="Very limited seating and quick service.",
        ),
    }
