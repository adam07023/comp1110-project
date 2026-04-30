from __future__ import annotations

from dataclasses import dataclass, field

from domain.models import TableInventory


@dataclass(frozen=True)
class GeneratorProfile:
    min_group_size: int
    max_group_size: int
    group_size_weights: dict[int, float]
    min_dining_duration: int
    max_dining_duration: int
    dining_duration_mean: float | None = None
    dining_duration_sd: float | None = None


@dataclass(frozen=True)
class BusinessModel:
    name: str
    queue_type: str
    strategy_name: str
    tables: list[TableInventory]
    generator_profile: GeneratorProfile
    patience_threshold_mean: float
    patience_threshold_sd: float
    servers: int = 1
    counter_order_time_min: int = 0
    counter_order_time_max: int = 0
    counter_order_time_mean: float = 0.0
    counter_order_time_sd: float = 0.0
    reservation_policy: str = "none"
    reserved_table_percent: float = 0.0
    reservation_hold_before_min: int = 0
    reservation_hold_after_min: int = 0
    arrival_pattern: str = "uniform"
    notes: str = field(default="")
