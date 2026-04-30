from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from domain.models import GroupArrival


@dataclass(frozen=True)
class QueueEntry:
    group: GroupArrival
    leave_time: int


class BaseQueueManager:
    def enqueue(self, group: GroupArrival, leave_time: int | None = None) -> None:
        raise NotImplementedError

    def remove(self, entry: QueueEntry) -> None:
        raise NotImplementedError

    def all_entries(self) -> list[QueueEntry]:
        raise NotImplementedError

    def size(self) -> int:
        return len(self.all_entries())

    def queue_lengths_by_label(self) -> dict[str, int]:
        return {"all": self.size()}


class SingleQueueManager(BaseQueueManager):
    def __init__(self) -> None:
        self._entries: deque[QueueEntry] = deque()

    def enqueue(self, group: GroupArrival, leave_time: int | None = None) -> None:
        fallback_leave_time = group.arrival_time + 10**9
        self._entries.append(
            QueueEntry(group=group, leave_time=leave_time if leave_time is not None else fallback_leave_time)
        )

    def remove(self, entry: QueueEntry) -> None:
        self._entries.remove(entry)

    def all_entries(self) -> list[QueueEntry]:
        return list(self._entries)


class GroupSizeQueueManager(BaseQueueManager):
    def __init__(self) -> None:
        self._queues: dict[str, deque[QueueEntry]] = defaultdict(deque)

    def _queue_label(self, group_size: int) -> str:
        if group_size <= 2:
            return "1-2"
        if group_size <= 4:
            return "3-4"
        return "5+"

    def enqueue(self, group: GroupArrival, leave_time: int | None = None) -> None:
        fallback_leave_time = group.arrival_time + 10**9
        self._queues[self._queue_label(group.group_size)].append(
            QueueEntry(group=group, leave_time=leave_time if leave_time is not None else fallback_leave_time)
        )

    def remove(self, entry: QueueEntry) -> None:
        self._queues[self._queue_label(entry.group.group_size)].remove(entry)

    def all_entries(self) -> list[QueueEntry]:
        entries: list[QueueEntry] = []
        for label in ("1-2", "3-4", "5+"):
            entries.extend(list(self._queues[label]))
        return sorted(entries, key=lambda item: (item.group.arrival_time, item.group.group_id))

    def queue_lengths_by_label(self) -> dict[str, int]:
        return {label: len(self._queues[label]) for label in ("1-2", "3-4", "5+")}


def build_queue_manager(queue_type: str) -> BaseQueueManager:
    if queue_type == "single_queue":
        return SingleQueueManager()
    if queue_type == "queue_by_group_size":
        return GroupSizeQueueManager()
    raise ValueError(f"Unknown queue type: {queue_type}")
