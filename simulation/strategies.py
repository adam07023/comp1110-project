from __future__ import annotations

from dataclasses import dataclass

from domain.models import Table
from simulation.queue_manager import BaseQueueManager, QueueEntry


@dataclass(frozen=True)
class SeatingChoice:
    entry: QueueEntry
    table: Table


def _fitting_entries(entries: list[QueueEntry], table: Table) -> list[QueueEntry]:
    return [entry for entry in entries if entry.group.group_size <= table.seats]


def _smallest_fitting_table(entry: QueueEntry, available_tables: list[Table]) -> Table | None:
    candidates = [table for table in available_tables if entry.group.group_size <= table.seats]
    if not candidates:
        return None
    return min(candidates, key=lambda table: (table.seats, table.table_id))


def choose_seating(
    strategy_name: str,
    queue_manager: BaseQueueManager,
    available_tables: list[Table],
) -> SeatingChoice | None:
    if not available_tables:
        return None

    entries = queue_manager.all_entries()
    if not entries:
        return None

    if strategy_name == "fifo_fit":
        for entry in sorted(entries, key=lambda item: (item.group.arrival_time, item.group.group_id)):
            table = _smallest_fitting_table(entry, available_tables)
            if table is not None:
                return SeatingChoice(entry=entry, table=table)
        return None

    if strategy_name == "strict_fifo_fit":
        head = min(entries, key=lambda item: (item.group.arrival_time, item.group.group_id))
        table = _smallest_fitting_table(head, available_tables)
        if table is None:
            return None
        return SeatingChoice(entry=head, table=table)

    if strategy_name == "smallest_table_fit":
        for table in sorted(available_tables, key=lambda item: (item.seats, item.table_id)):
            fitting_entries = _fitting_entries(entries, table)
            if fitting_entries:
                chosen_entry = min(
                    fitting_entries,
                    key=lambda item: (item.group.arrival_time, item.group.group_id),
                )
                return SeatingChoice(entry=chosen_entry, table=table)
        return None

    if strategy_name == "best_fit":
        best: SeatingChoice | None = None
        best_score: tuple[int, int, int, str] | None = None
        for table in available_tables:
            for entry in _fitting_entries(entries, table):
                spare = table.seats - entry.group.group_size
                score = (spare, entry.group.arrival_time, -entry.group.group_size, table.table_id)
                if best_score is None or score < best_score:
                    best_score = score
                    best = SeatingChoice(entry=entry, table=table)
        return best

    raise ValueError(f"Unknown strategy name: {strategy_name}")
