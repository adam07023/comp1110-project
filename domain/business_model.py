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
    notes: str = field(default="")
