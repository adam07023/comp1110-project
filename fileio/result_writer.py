from __future__ import annotations

from pathlib import Path

from domain.models import SimulationResult


def write_result_file(path: Path, result: SimulationResult) -> None:
    lines = [
        "[summary]",
        f"business_model={result.scenario.business_model_name}",
        f"queue_type={result.scenario.queue_type}",
        f"strategy={result.scenario.strategy_name}",
        "",
        "[tables]",
        "# seats_per_table, table_count",
    ]
    lines.extend(f"{table.seats},{table.count}" for table in result.scenario.tables)
    lines.extend(
        [
            "",
            "[arrivals]",
            "# arrival_time, group_size, dining_duration, patience, is_reservation, scheduled_time",
        ]
    )
    lines.extend(
        (
            f"{arrival.arrival_time},{arrival.group_size},{arrival.dining_duration},"
            f"{'' if arrival.patience_override is None else arrival.patience_override},"
            f"{str(arrival.is_reservation).lower()},"
            f"{'' if arrival.scheduled_time is None else arrival.scheduled_time}"
        )
        for arrival in result.scenario.arrivals
    )
    lines.extend(
        [
            "",
        "[statistics]",
        result.statistics.to_pretty_text(),
        "",
        "[rejections]",
        "# group_id, reason",
        ]
    )
    lines.extend(
        f"{rejection.group.group_id},{rejection.reason}" for rejection in result.rejected
    )
    lines.extend(
        [
            "",
            "[event_log]",
            "# timestamp, event_type, group_id, table_id, queue_size, message, metadata",
        ]
    )
    for event in result.events:
        metadata = ";".join(f"{key}={value}" for key, value in sorted(event.metadata.items()))
        lines.append(
            f"{event.timestamp},{event.event_type},{event.group_id or ''},{event.table_id or ''},"
            f"{'' if event.queue_size is None else event.queue_size},{event.message},{metadata}"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
