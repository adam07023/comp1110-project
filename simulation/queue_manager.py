from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from domain.models import GroupArrival


@dataclass(frozen=True)
class QueueEntry:
    group: GroupArrival


class BaseQueueManager:
    def enqueue(self, group: GroupArrival) -> None:
        raise NotImplementedError

    def remove(self, entry: QueueEntry) -> None:
        raise NotImplementedError

    def all_entries(self) -> list[QueueEntry]:
        raise NotImplementedError

    def size(self) -> int:
        return len(self.all_entries())


class SingleQueueManager(BaseQueueManager):
    def __init__(self) -> None:
        self._entries: deque[QueueEntry] = deque()

    def enqueue(self, group: GroupArrival) -> None:
        self._entries.append(QueueEntry(group))

    def remove(self, entry: QueueEntry) -> None:
        self._entries.remove(entry)

    def all_entries(self) -> list[QueueEntry]:
        return list(self._entries)


class GroupSizeQueueManager(BaseQueueManager):
    def __init__(self) -> None:
        self._queues: dict[int, deque[QueueEntry]] = defaultdict(deque)

    def enqueue(self, group: GroupArrival) -> None:
        self._queues[group.group_size].append(QueueEntry(group))

    def remove(self, entry: QueueEntry) -> None:
        self._queues[entry.group.group_size].remove(entry)

    def all_entries(self) -> list[QueueEntry]:
        entries: list[QueueEntry] = []
        for group_size in sorted(self._queues):
            entries.extend(list(self._queues[group_size]))
        return sorted(entries, key=lambda item: (item.group.arrival_time, item.group.group_id))


def build_queue_manager(queue_type: str) -> BaseQueueManager:
    if queue_type == "single_queue":
        return SingleQueueManager()
    if queue_type == "queue_by_group_size":
        return GroupSizeQueueManager()
    raise ValueError(f"Unknown queue type: {queue_type}")
