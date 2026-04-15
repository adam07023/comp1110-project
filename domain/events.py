from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SimulationEvent:
    timestamp: int
    event_type: str
    group_id: str | None = None
    table_id: str | None = None
    message: str = ""
    queue_size: int | None = None
    metadata: dict[str, int | str] = field(default_factory=dict)
