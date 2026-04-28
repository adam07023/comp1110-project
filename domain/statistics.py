from __future__ import annotations

from collections import defaultdict

from domain.models import GroupArrival, RejectedGroup, SeatedGroup, SimulationStatistics, Table


def compute_statistics(
    arrivals: list[GroupArrival],
    seated_groups: list[SeatedGroup],
    rejected_groups: list[RejectedGroup],
    tables: list[Table],
    queue_lengths: list[int] | None = None,
    server_busy_time: int = 0,
    server_count: int = 0,
    kiosk_busy_time: int = 0,
    kiosk_count: int = 0,
    reservation_no_shows: int = 0,
    reservation_tables_released: int = 0,
) -> SimulationStatistics:
    waits = [seated.seated_time - seated.group.arrival_time for seated in seated_groups]
    waits_by_size: dict[int, list[int]] = defaultdict(list)
    ordering_waits: list[int] = []
    seating_waits: list[int] = []
    ordering_waits_by_size: dict[int, list[int]] = defaultdict(list)
    seating_waits_by_size: dict[int, list[int]] = defaultdict(list)
    for seated in seated_groups:
        waits_by_size[seated.group.group_size].append(seated.seated_time - seated.group.arrival_time)
        ordering_wait = (
            0
            if seated.order_start_time is None
            else seated.order_start_time - seated.group.arrival_time
        )
        seating_start = (
            seated.group.arrival_time
            if seated.seating_queue_enter_time is None
            else seated.seating_queue_enter_time
        )
        seating_wait = seated.seated_time - seating_start
        ordering_waits.append(ordering_wait)
        seating_waits.append(seating_wait)
        ordering_waits_by_size[seated.group.group_size].append(ordering_wait)
        seating_waits_by_size[seated.group.group_size].append(seating_wait)

    simulation_end_time = 0
    if seated_groups:
        simulation_end_time = max(seated.departure_time for seated in seated_groups)
    elif arrivals:
        simulation_end_time = max(arrival.arrival_time for arrival in arrivals)

    occupied_table_time = sum(seated.departure_time - seated.seated_time for seated in seated_groups)
    table_count = len(tables)
    denominator = simulation_end_time * table_count if simulation_end_time > 0 and table_count > 0 else 0
    utilization = occupied_table_time / denominator if denominator else 0.0

    average_wait_by_group_size = {
        group_size: sum(group_waits) / len(group_waits)
        for group_size, group_waits in waits_by_size.items()
    }
    average_ordering_wait_by_group_size = {
        group_size: sum(group_waits) / len(group_waits)
        for group_size, group_waits in ordering_waits_by_size.items()
    }
    average_seating_wait_by_group_size = {
        group_size: sum(group_waits) / len(group_waits)
        for group_size, group_waits in seating_waits_by_size.items()
    }

    longest_queue = max(queue_lengths) if queue_lengths else 0
    shortest_queue = min(queue_lengths) if queue_lengths else 0
    server_denominator = simulation_end_time * server_count if simulation_end_time > 0 else 0
    kiosk_denominator = simulation_end_time * kiosk_count if simulation_end_time > 0 else 0

    return SimulationStatistics(
        served_groups=len(seated_groups),
        rejected_groups=len(rejected_groups),
        total_groups=len(arrivals),
        average_wait_time=sum(waits) / len(waits) if waits else 0.0,
        min_wait_time=min(waits) if waits else None,
        max_wait_time=max(waits) if waits else None,
        longest_queue_length=longest_queue,
        shortest_queue_length=shortest_queue,
        table_utilization_rate=utilization,
        simulation_end_time=simulation_end_time,
        average_wait_by_group_size=average_wait_by_group_size,
        average_ordering_wait_time=sum(ordering_waits) / len(ordering_waits) if ordering_waits else 0.0,
        average_seating_wait_time=sum(seating_waits) / len(seating_waits) if seating_waits else 0.0,
        average_ordering_wait_by_group_size=average_ordering_wait_by_group_size,
        average_seating_wait_by_group_size=average_seating_wait_by_group_size,
        server_utilization_rate=server_busy_time / server_denominator if server_denominator else 0.0,
        kiosk_utilization_rate=kiosk_busy_time / kiosk_denominator if kiosk_denominator else 0.0,
        abandoned_at_ordering=sum(
            1 for rejection in rejected_groups if rejection.reason == "left_due_to_patience" and rejection.stage == "ordering"
        ),
        abandoned_at_seating=sum(
            1 for rejection in rejected_groups if rejection.reason == "left_due_to_patience" and rejection.stage == "seating"
        ),
        reservation_groups_served=sum(1 for seated in seated_groups if seated.group.is_reservation),
        reservation_no_shows=reservation_no_shows,
        reservation_tables_released=reservation_tables_released,
    )
