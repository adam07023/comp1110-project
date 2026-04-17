from __future__ import annotations

import heapq
import random
from collections import defaultdict

from domain.events import SimulationEvent
from domain.models import GroupArrival, RejectedGroup, Scenario, SeatedGroup, SimulationResult
from domain.statistics import compute_statistics
from generation.validators import validate_scenario
from simulation.allocator import expand_tables
from simulation.queue_manager import build_queue_manager
from simulation.strategies import choose_seating


def _sample_patience_threshold(mean: float, sd: float, rng: random.Random) -> int:
    sampled = rng.gauss(mean, sd)
    return max(1, int(round(sampled)))


def _record_event(
    events: list[SimulationEvent],
    timestamp: int,
    event_type: str,
    queue_size: int,
    group_id: str | None = None,
    table_id: str | None = None,
    message: str = "",
    **metadata: int | str,
) -> None:
    events.append(
        SimulationEvent(
            timestamp=timestamp,
            event_type=event_type,
            group_id=group_id,
            table_id=table_id,
            message=message,
            queue_size=queue_size,
            metadata=metadata,
        )
    )


def run_simulation(scenario: Scenario) -> SimulationResult:
    validate_scenario(scenario)

    tables = expand_tables(scenario.tables)
    available_tables = {table.table_id: table for table in tables}
    seated_by_table: dict[str, SeatedGroup] = {}
    departures: list[tuple[int, str]] = []
    queue_manager = build_queue_manager(scenario.queue_type)
    rng = random.Random(scenario.seed)

    arrivals = sorted(scenario.arrivals, key=lambda arrival: (arrival.arrival_time, arrival.group_id))
    arrivals_by_time: dict[int, list[GroupArrival]] = defaultdict(list)
    for arrival in arrivals:
        arrivals_by_time[arrival.arrival_time].append(arrival)

    max_table_size = max((table.seats for table in tables), default=0)
    events: list[SimulationEvent] = []
    rejected: list[RejectedGroup] = []
    seated_groups: list[SeatedGroup] = []
    queue_lengths: list[int] = [0]

    pending_times = sorted(arrivals_by_time)
    time_cursor = 0

    while pending_times or departures or queue_manager.size() > 0:
        next_arrival_time = pending_times[0] if pending_times else None
        next_departure_time = departures[0][0] if departures else None
        next_leave_time = min((entry.leave_time for entry in queue_manager.all_entries()), default=None)

        candidate_times = [
            time for time in (next_arrival_time, next_departure_time, next_leave_time) if time is not None
        ]
        time_cursor = min(candidate_times)

        while departures and departures[0][0] == time_cursor:
            _, table_id = heapq.heappop(departures)
            seated = seated_by_table.pop(table_id)
            available_tables[table_id] = next(table for table in tables if table.table_id == table_id)
            _record_event(
                events,
                timestamp=time_cursor,
                event_type="departure",
                group_id=seated.group.group_id,
                table_id=table_id,
                queue_size=queue_manager.size(),
                message=f"Group {seated.group.group_id} left table {table_id}",
            )

        for arrival in arrivals_by_time.pop(time_cursor, []):
            if arrival.group_size > max_table_size:
                rejection = RejectedGroup(
                    group=arrival,
                    reason="group_exceeds_largest_table",
                )
                rejected.append(rejection)
                _record_event(
                    events,
                    timestamp=time_cursor,
                    event_type="rejection",
                    group_id=arrival.group_id,
                    queue_size=queue_manager.size(),
                    message=f"Rejected group {arrival.group_id}: no table can seat {arrival.group_size}",
                    group_size=arrival.group_size,
                )
                continue

            patience_threshold = _sample_patience_threshold(
                mean=scenario.patience_threshold_mean,
                sd=scenario.patience_threshold_sd,
                rng=rng,
            )
            leave_time = arrival.arrival_time + patience_threshold
            queue_manager.enqueue(arrival, leave_time=leave_time)
            _record_event(
                events,
                timestamp=time_cursor,
                event_type="arrival",
                group_id=arrival.group_id,
                queue_size=queue_manager.size(),
                message=f"Group {arrival.group_id} arrived",
                group_size=arrival.group_size,
                dining_duration=arrival.dining_duration,
                patience_threshold=patience_threshold,
                leave_time=leave_time,
            )

        if pending_times and pending_times[0] == time_cursor:
            pending_times.pop(0)

        entries_leaving = sorted(
            [entry for entry in queue_manager.all_entries() if entry.leave_time <= time_cursor],
            key=lambda item: (item.leave_time, item.group.arrival_time, item.group.group_id),
        )
        for leaving_entry in entries_leaving:
            queue_manager.remove(leaving_entry)
            rejection = RejectedGroup(
                group=leaving_entry.group,
                reason="left_due_to_patience",
            )
            rejected.append(rejection)
            _record_event(
                events,
                timestamp=time_cursor,
                event_type="abandonment",
                group_id=leaving_entry.group.group_id,
                queue_size=queue_manager.size(),
                message=f"Group {leaving_entry.group.group_id} left the queue due to patience limit",
                waited_time=time_cursor - leaving_entry.group.arrival_time,
            )

        while True:
            choice = choose_seating(
                strategy_name=scenario.strategy_name,
                queue_manager=queue_manager,
                available_tables=sorted(available_tables.values(), key=lambda table: (table.seats, table.table_id)),
            )
            if choice is None:
                break

            queue_manager.remove(choice.entry)
            table = available_tables.pop(choice.table.table_id)
            departure_time = time_cursor + choice.entry.group.dining_duration
            seated = SeatedGroup(
                group=choice.entry.group,
                table_id=table.table_id,
                seated_time=time_cursor,
                departure_time=departure_time,
            )
            seated_by_table[table.table_id] = seated
            seated_groups.append(seated)
            heapq.heappush(departures, (departure_time, table.table_id))
            _record_event(
                events,
                timestamp=time_cursor,
                event_type="seating",
                group_id=choice.entry.group.group_id,
                table_id=table.table_id,
                queue_size=queue_manager.size(),
                message=f"Seated group {choice.entry.group.group_id} at table {table.table_id}",
                wait_time=time_cursor - choice.entry.group.arrival_time,
                table_size=table.seats,
            )

        queue_lengths.append(queue_manager.size())

    statistics = compute_statistics(arrivals, seated_groups, rejected, tables)
    statistics.longest_queue_length = max(queue_lengths) if queue_lengths else 0
    statistics.shortest_queue_length = min(queue_lengths) if queue_lengths else 0

    return SimulationResult(
        scenario=scenario,
        events=events,
        statistics=statistics,
        rejected=rejected,
        seated_groups=seated_groups,
    )
