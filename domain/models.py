from __future__ import annotations

from dataclasses import dataclass, field

from domain.events import SimulationEvent


@dataclass(frozen=True)
class TableInventory:
    seats: int
    count: int


@dataclass(frozen=True)
class Table:
    table_id: str
    seats: int


@dataclass(frozen=True)
class GroupArrival:
    group_id: str
    arrival_time: int
    group_size: int
    dining_duration: int


@dataclass(frozen=True)
class SeatedGroup:
    group: GroupArrival
    table_id: str
    seated_time: int
    departure_time: int


@dataclass(frozen=True)
class Scenario:
    business_model_name: str
    queue_type: str
    strategy_name: str
    tables: list[TableInventory]
    arrivals: list[GroupArrival]
    patience_threshold_mean: float = 45.0
    patience_threshold_sd: float = 10.0
    seed: int | None = None
    generated: bool = False


@dataclass(frozen=True)
class RejectedGroup:
    group: GroupArrival
    reason: str


@dataclass
class SimulationStatistics:
    served_groups: int
    rejected_groups: int
    total_groups: int
    average_wait_time: float
    min_wait_time: int | None
    max_wait_time: int | None
    longest_queue_length: int
    shortest_queue_length: int
    table_utilization_rate: float
    simulation_end_time: int
    average_wait_by_group_size: dict[int, float] = field(default_factory=dict)

    def to_pretty_text(self) -> str:
        lines = [
            f"served_groups={self.served_groups}",
            f"rejected_groups={self.rejected_groups}",
            f"total_groups={self.total_groups}",
            f"average_wait_time={self.average_wait_time:.2f}",
            f"min_wait_time={self.min_wait_time}",
            f"max_wait_time={self.max_wait_time}",
            f"longest_queue_length={self.longest_queue_length}",
            f"shortest_queue_length={self.shortest_queue_length}",
            f"table_utilization_rate={self.table_utilization_rate:.4f}",
            f"simulation_end_time={self.simulation_end_time}",
        ]
        for group_size, average_wait in sorted(self.average_wait_by_group_size.items()):
            lines.append(f"average_wait_group_size_{group_size}={average_wait:.2f}")
        return "\n".join(lines)


@dataclass(frozen=True)
class SimulationResult:
    scenario: Scenario
    events: list[SimulationEvent]
    statistics: SimulationStatistics
    rejected: list[RejectedGroup]
    seated_groups: list[SeatedGroup]
