from __future__ import annotations

import heapq
import random
from collections import deque
from dataclasses import dataclass
from itertools import count

from domain.events import SimulationEvent
from domain.models import GroupArrival, RejectedGroup, Scenario, SeatedGroup, SimulationResult
from domain.statistics import compute_statistics
from generation.randomizer import _patience_bounds, _sample_truncated_normal
from generation.validators import validate_scenario
from simulation.allocator import expand_tables
from simulation.queue_manager import BaseQueueManager, QueueEntry
from simulation.queue_manager import build_queue_manager
from simulation.strategies import choose_seating

EVENT_PRIORITY = {
    "departure": 0,
    "reservation_release": 1,
    "reservation_hold": 2,
    "abandonment": 3,
    "order_complete": 4,
    "arrival": 5,
}

SERVICE_LEVEL_THRESHOLDS = {
    "fast_food": 10,
    "fine_dining": 30,
    "casual_dining": 20,
    "cafe": 8,
    "food_truck": 5,
}


@dataclass
class GroupState:
    group: GroupArrival
    leave_time: int
    status: str
    order_channel: str | None = None
    order_start_time: int | None = None
    order_complete_time: int | None = None
    seating_queue_enter_time: int | None = None
    service_start_time: int | None = None
    service_end_time: int | None = None


class ListQueueManager(BaseQueueManager):
    def __init__(self, entries: list[QueueEntry]) -> None:
        self._entries = entries

    def enqueue(self, group: GroupArrival, leave_time: int | None = None) -> None:
        self._entries.append(QueueEntry(group=group, leave_time=leave_time or 0))

    def remove(self, entry: QueueEntry) -> None:
        self._entries.remove(entry)

    def all_entries(self) -> list[QueueEntry]:
        return list(self._entries)


def _sample_patience_threshold(mean: float, sd: float, rng: random.Random) -> int:
    minimum, maximum = _patience_bounds(mean, sd)
    return _sample_truncated_normal(minimum=minimum, maximum=maximum, mean=mean, sd=sd, rng=rng)


def _order_duration(scenario: Scenario, rng: random.Random) -> int:
    return _sample_truncated_normal(
        scenario.counter_order_time_min,
        scenario.counter_order_time_max,
        scenario.counter_order_time_mean,
        scenario.counter_order_time_sd,
        rng,
    )


def _service_level_threshold_for_model(model_name: str) -> int:
    return SERVICE_LEVEL_THRESHOLDS.get(model_name, 10)


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

    bypass_ordering = scenario.business_model_name == "food_truck"
    tables = expand_tables(scenario.tables)
    available_tables = {table.table_id: table for table in tables}
    held_tables: set[str] = set()
    reserved_tables = {
        table.table_id
        for table in sorted(tables, key=lambda item: (-item.seats, item.table_id))[
            : int(len(tables) * scenario.reserved_table_percent)
        ]
    }
    seated_by_table: dict[str, SeatedGroup] = {}
    seating_queue = build_queue_manager(scenario.queue_type)
    ordering_queue: deque[str] = deque()
    rng = random.Random(scenario.seed)
    sequence = count()
    event_queue: list[tuple[int, int, int, str, str | None, dict[str, object]]] = []

    arrivals = sorted(scenario.arrivals, key=lambda arrival: (arrival.arrival_time, arrival.group_id))
    max_table_size = max((table.seats for table in tables), default=0)
    events: list[SimulationEvent] = []
    rejected: list[RejectedGroup] = []
    seated_groups: list[SeatedGroup] = []
    queue_lengths: list[int] = [0]
    queue_length_snapshots: list[dict[str, int]] = [seating_queue.queue_lengths_by_label()]
    states: dict[str, GroupState] = {}
    server_available = scenario.servers
    server_busy_time = 0
    reservation_tables_released = 0
    reservation_no_shows = 0

    def schedule(
        timestamp: int,
        event_type: str,
        group_id: str | None = None,
        **payload: object,
    ) -> None:
        heapq.heappush(
            event_queue,
            (
                timestamp,
                EVENT_PRIORITY.get(event_type, 50),
                next(sequence),
                event_type,
                group_id,
                payload,
            ),
        )

    for arrival in arrivals:
        schedule(arrival.arrival_time, "arrival", arrival.group_id, group=arrival)
        if scenario.reservation_policy == "hybrid_allocation" and arrival.is_reservation:
            schedule(
                max(0, (arrival.scheduled_time or arrival.arrival_time) - scenario.reservation_hold_before_min),
                "reservation_hold",
                arrival.group_id,
            )
            schedule(
                (arrival.scheduled_time or arrival.arrival_time) + scenario.reservation_hold_after_min,
                "reservation_release",
                arrival.group_id,
            )

    def total_waiting() -> int:
        return len(ordering_queue) + seating_queue.size()

    def record_queue_length() -> None:
        queue_lengths.append(total_waiting())
        queue_length_snapshots.append(seating_queue.queue_lengths_by_label())

    def enqueue_seating(state: GroupState, timestamp: int) -> None:
        state.status = "seating_queue"
        state.seating_queue_enter_time = timestamp
        seating_queue.enqueue(state.group, leave_time=state.leave_time)
        if scenario.strategy_name == "exact_match" and not any(
            table.seats == state.group.group_size for table in tables
        ):
            _record_event(
                events,
                timestamp=timestamp,
                event_type="starvation",
                group_id=state.group.group_id,
                queue_size=total_waiting(),
                message=f"Group {state.group.group_id} has no exact-match table",
                group_size=state.group.group_size,
            )

    def release_order_resource(state: GroupState, timestamp: int) -> None:
        nonlocal server_available, server_busy_time
        server_available += 1
        if state.service_start_time is not None:
            server_busy_time += max(0, timestamp - state.service_start_time)
        state.service_start_time = None
        state.service_end_time = None

    def try_start_orders(timestamp: int) -> None:
        nonlocal server_available
        while ordering_queue and server_available > 0:
            group_id = ordering_queue.popleft()
            state = states[group_id]
            if state.status != "ordering_queue":
                continue
            if state.leave_time <= timestamp:
                schedule(timestamp, "abandonment", group_id)
                continue
            server_available -= 1
            duration = _order_duration(scenario, rng)
            state.status = "ordering_service"
            state.order_channel = "server"
            state.order_start_time = timestamp
            state.service_start_time = timestamp
            state.service_end_time = timestamp + duration
            _record_event(
                events,
                timestamp=timestamp,
                event_type="order_start",
                group_id=group_id,
                queue_size=total_waiting(),
                message=f"Group {group_id} started ordering",
                order_duration=duration,
            )
            schedule(timestamp + duration, "order_complete", group_id)

    def entries_for(reservation_status: bool) -> list[QueueEntry]:
        return [
            entry
            for entry in seating_queue.all_entries()
            if entry.group.is_reservation is reservation_status
        ]

    def try_seating_for(
        timestamp: int,
        reservation_status: bool,
        allowed_table_ids: set[str],
    ) -> bool:
        entries = entries_for(reservation_status)
        if not entries or not allowed_table_ids:
            return False
        choices = [available_tables[table_id] for table_id in allowed_table_ids if table_id in available_tables]
        choice = choose_seating(scenario.strategy_name, ListQueueManager(entries), sorted(choices, key=lambda table: (table.seats, table.table_id)))
        if choice is None:
            return False
        seating_queue.remove(choice.entry)
        table = available_tables.pop(choice.table.table_id)
        departure_time = timestamp + choice.entry.group.dining_duration
        state = states[choice.entry.group.group_id]
        state.status = "seated"
        if choice.entry.group.is_reservation:
            held_tables.discard(table.table_id)
        seated = SeatedGroup(
            group=choice.entry.group,
            table_id=table.table_id,
            seated_time=timestamp,
            departure_time=departure_time,
            order_start_time=state.order_start_time,
            order_complete_time=state.order_complete_time,
            seating_queue_enter_time=state.seating_queue_enter_time,
            order_channel=state.order_channel,
        )
        seated_by_table[table.table_id] = seated
        seated_groups.append(seated)
        schedule(departure_time, "departure", table_id=table.table_id)
        _record_event(
            events,
            timestamp=timestamp,
            event_type="seated",
            group_id=choice.entry.group.group_id,
            table_id=table.table_id,
            queue_size=total_waiting(),
            message=f"Seated group {choice.entry.group.group_id} at table {table.table_id}",
            wait_time=timestamp - choice.entry.group.arrival_time,
            table_size=table.seats,
        )
        return True

    def try_seating(timestamp: int) -> None:
        while True:
            seated_reservation = try_seating_for(timestamp, True, set(available_tables))
            walk_in_ids = set(available_tables) - held_tables
            seated_walk_in = try_seating_for(timestamp, False, walk_in_ids)
            if not seated_reservation and not seated_walk_in:
                break
        record_queue_length()

    def abandon(group_id: str, timestamp: int) -> None:
        state = states.get(group_id)
        if state is None or state.status in {"abandoned", "seated", "departed", "rejected"}:
            return
        stage = "ordering" if state.status.startswith("ordering") else "seating"
        if state.status == "ordering_queue":
            try:
                ordering_queue.remove(group_id)
            except ValueError:
                pass
        elif state.status == "ordering_service":
            release_order_resource(state, timestamp)
        elif state.status == "seating_queue":
            for entry in seating_queue.all_entries():
                if entry.group.group_id == group_id:
                    seating_queue.remove(entry)
                    break
        state.status = "abandoned"
        rejected.append(RejectedGroup(group=state.group, reason="left_due_to_patience", stage=stage))
        _record_event(
            events,
            timestamp=timestamp,
            event_type="abandonment",
            group_id=group_id,
            queue_size=total_waiting(),
            message=f"Group {group_id} left during {stage} due to patience limit",
            waited_time=timestamp - state.group.arrival_time,
            stage=stage,
        )
        try_start_orders(timestamp)
        try_seating(timestamp)

    while event_queue:
        time_cursor, _priority, _seq, event_type, group_id, payload = heapq.heappop(event_queue)

        if event_type == "departure":
            table_id = str(payload["table_id"])
            seated = seated_by_table.pop(table_id)
            states[seated.group.group_id].status = "departed"
            available_tables[table_id] = next(table for table in tables if table.table_id == table_id)
            _record_event(
                events,
                timestamp=time_cursor,
                event_type="departure",
                group_id=seated.group.group_id,
                table_id=table_id,
                queue_size=total_waiting(),
                message=f"Group {seated.group.group_id} left table {table_id}",
            )
            try_seating(time_cursor)
            continue

        if event_type == "reservation_release":
            if not group_id:
                continue
            state = states.get(group_id)
            if state is None:
                reservation_no_shows += 1
            if state is None or state.status in {"abandoned", "rejected"}:
                for table_id in list(held_tables):
                    if table_id in reserved_tables:
                        held_tables.remove(table_id)
                        if table_id not in seated_by_table:
                            available_tables[table_id] = next(table for table in tables if table.table_id == table_id)
                        reservation_tables_released += 1
                        _record_event(
                            events,
                            timestamp=time_cursor,
                            event_type="reservation_release",
                            group_id=group_id,
                            table_id=table_id,
                            queue_size=total_waiting(),
                            message=f"Released reserved table {table_id}",
                        )
                        break
            try_seating(time_cursor)
            continue

        if event_type == "reservation_hold":
            available_reserved = [
                table for table in available_tables.values() if table.table_id in reserved_tables
            ]
            if available_reserved:
                table = max(available_reserved, key=lambda item: (item.seats, item.table_id))
                held_tables.add(table.table_id)
                _record_event(
                    events,
                    timestamp=time_cursor,
                    event_type="reservation_hold",
                    group_id=group_id,
                    table_id=table.table_id,
                    queue_size=total_waiting(),
                    message=f"Held reserved table {table.table_id}",
                )
            continue

        if event_type == "abandonment":
            if group_id is not None:
                abandon(group_id, time_cursor)
            continue

        if event_type == "order_complete":
            if group_id is None:
                continue
            state = states.get(group_id)
            if state is None or state.status != "ordering_service":
                continue
            release_order_resource(state, time_cursor)
            state.order_complete_time = time_cursor
            _record_event(
                events,
                timestamp=time_cursor,
                event_type="order_complete",
                group_id=group_id,
                queue_size=total_waiting(),
                message=f"Group {group_id} completed ordering",
            )
            if state.leave_time <= time_cursor:
                abandon(group_id, time_cursor)
            else:
                enqueue_seating(state, time_cursor)
                try_start_orders(time_cursor)
                try_seating(time_cursor)
            continue

        if event_type == "arrival":
            arrival = payload["group"]
            assert isinstance(arrival, GroupArrival)
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
                    queue_size=total_waiting(),
                    message=f"Rejected group {arrival.group_id}: no table can seat {arrival.group_size}",
                    group_size=arrival.group_size,
                )
                continue

            patience_threshold = (
                arrival.patience_override
                if arrival.patience_override is not None
                else _sample_patience_threshold(
                    mean=scenario.patience_threshold_mean,
                    sd=scenario.patience_threshold_sd,
                    rng=rng,
                )
            )
            leave_time = arrival.arrival_time + patience_threshold
            state = GroupState(group=arrival, leave_time=leave_time, status="arrived")
            states[arrival.group_id] = state
            _record_event(
                events,
                timestamp=time_cursor,
                event_type="arrival",
                group_id=arrival.group_id,
                queue_size=total_waiting(),
                message=f"Group {arrival.group_id} arrived",
                group_size=arrival.group_size,
                dining_duration=arrival.dining_duration,
                patience_threshold=patience_threshold,
                leave_time=leave_time,
            )
            if leave_time <= time_cursor:
                abandon(arrival.group_id, time_cursor)
                continue
            schedule(leave_time, "abandonment", arrival.group_id)
            if arrival.is_reservation or bypass_ordering:
                enqueue_seating(state, time_cursor)
                try_seating(time_cursor)
            else:
                state.status = "ordering_queue"
                ordering_queue.append(arrival.group_id)
                record_queue_length()
                try_start_orders(time_cursor)
                try_seating(time_cursor)

    statistics = compute_statistics(
        arrivals,
        seated_groups,
        rejected,
        tables,
        queue_lengths,
        queue_length_snapshots=queue_length_snapshots,
        server_busy_time=server_busy_time,
        server_count=scenario.servers,
        reservation_no_shows=reservation_no_shows,
        reservation_tables_released=reservation_tables_released,
        service_level_threshold=_service_level_threshold_for_model(scenario.business_model_name),
    )

    return SimulationResult(
        scenario=scenario,
        events=events,
        statistics=statistics,
        rejected=rejected,
        seated_groups=seated_groups,
    )
