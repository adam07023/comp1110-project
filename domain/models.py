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
    patience_override: int | None = None
    is_reservation: bool = False
    scheduled_time: int | None = None


@dataclass(frozen=True)
class SeatedGroup:
    group: GroupArrival
    table_id: str
    seated_time: int
    departure_time: int
    order_start_time: int | None = None
    order_complete_time: int | None = None
    seating_queue_enter_time: int | None = None
    order_channel: str | None = None


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
    servers: int = 1
    ordering_type: str = "counter_only"
    counter_order_time_min: int = 0
    counter_order_time_max: int = 0
    counter_order_time_mean: float = 0.0
    counter_order_time_sd: float = 0.0
    kiosks: int = 0
    kiosk_usage_percent: float = 0.0
    kiosk_order_time_min: int = 0
    kiosk_order_time_max: int = 0
    kiosk_order_time_mean: float = 0.0
    kiosk_order_time_sd: float = 0.0
    reservation_policy: str = "none"
    reserved_table_percent: float = 0.0
    reservation_hold_before_min: int = 0
    reservation_hold_after_min: int = 0


@dataclass(frozen=True)
class RejectedGroup:
    group: GroupArrival
    reason: str
    stage: str | None = None


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
    average_ordering_wait_time: float = 0.0
    average_seating_wait_time: float = 0.0
    average_ordering_wait_by_group_size: dict[int, float] = field(default_factory=dict)
    average_seating_wait_by_group_size: dict[int, float] = field(default_factory=dict)
    server_utilization_rate: float = 0.0
    kiosk_utilization_rate: float = 0.0
    abandoned_at_ordering: int = 0
    abandoned_at_seating: int = 0
    reservation_groups_served: int = 0
    reservation_no_shows: int = 0
    reservation_tables_released: int = 0

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
            f"average_ordering_wait_time={self.average_ordering_wait_time:.2f}",
            f"average_seating_wait_time={self.average_seating_wait_time:.2f}",
            f"server_utilization_rate={self.server_utilization_rate:.4f}",
            f"kiosk_utilization_rate={self.kiosk_utilization_rate:.4f}",
            f"abandoned_at_ordering={self.abandoned_at_ordering}",
            f"abandoned_at_seating={self.abandoned_at_seating}",
            f"reservation_groups_served={self.reservation_groups_served}",
            f"reservation_no_shows={self.reservation_no_shows}",
            f"reservation_tables_released={self.reservation_tables_released}",
        ]
        for group_size, average_wait in sorted(self.average_wait_by_group_size.items()):
            lines.append(f"average_wait_group_size_{group_size}={average_wait:.2f}")
        for group_size, average_wait in sorted(self.average_ordering_wait_by_group_size.items()):
            lines.append(f"average_ordering_wait_group_size_{group_size}={average_wait:.2f}")
        for group_size, average_wait in sorted(self.average_seating_wait_by_group_size.items()):
            lines.append(f"average_seating_wait_group_size_{group_size}={average_wait:.2f}")
        return "\n".join(lines)


@dataclass(frozen=True)
class SimulationResult:
    scenario: Scenario
    events: list[SimulationEvent]
    statistics: SimulationStatistics
    rejected: list[RejectedGroup]
    seated_groups: list[SeatedGroup]
