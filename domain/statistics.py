from __future__ import annotations

from collections import defaultdict

from domain.models import GroupArrival, RejectedGroup, SeatedGroup, SimulationStatistics, Table


def compute_statistics(
    arrivals: list[GroupArrival],
    seated_groups: list[SeatedGroup],
    rejected_groups: list[RejectedGroup],
    tables: list[Table],
    queue_lengths: list[int] | None = None,
) -> SimulationStatistics:
    waits = [seated.seated_time - seated.group.arrival_time for seated in seated_groups]
    waits_by_size: dict[int, list[int]] = defaultdict(list)
    for seated in seated_groups:
        waits_by_size[seated.group.group_size].append(seated.seated_time - seated.group.arrival_time)

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

    longest_queue = max(queue_lengths) if queue_lengths else 0
    shortest_queue = min(queue_lengths) if queue_lengths else 0

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
    )
