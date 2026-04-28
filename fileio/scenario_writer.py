from __future__ import annotations

from pathlib import Path

from domain.models import Scenario
from generation.seed_store import seed_metadata


def write_scenario_file(path: Path, scenario: Scenario) -> None:
    seed = seed_metadata(scenario)
    lines = [
        "[business_model]",
        f"name={scenario.business_model_name}",
        "",
        "[queue]",
        f"type={scenario.queue_type}",
        f"strategy={scenario.strategy_name}",
        "",
        "[patience]",
        f"mean_threshold={scenario.patience_threshold_mean}",
        f"sd_threshold={scenario.patience_threshold_sd}",
        "",
        "[ordering]",
        f"type={scenario.ordering_type}",
        f"servers={scenario.servers}",
        f"counter_min={scenario.counter_order_time_min}",
        f"counter_max={scenario.counter_order_time_max}",
        f"counter_mean={scenario.counter_order_time_mean}",
        f"counter_sd={scenario.counter_order_time_sd}",
        f"kiosks={scenario.kiosks}",
        f"kiosk_usage_percent={scenario.kiosk_usage_percent}",
        f"kiosk_min={scenario.kiosk_order_time_min}",
        f"kiosk_max={scenario.kiosk_order_time_max}",
        f"kiosk_mean={scenario.kiosk_order_time_mean}",
        f"kiosk_sd={scenario.kiosk_order_time_sd}",
        "",
        "[reservations]",
        f"policy={scenario.reservation_policy}",
        f"reserved_table_percent={scenario.reserved_table_percent}",
        f"hold_before_min={scenario.reservation_hold_before_min}",
        f"hold_after_min={scenario.reservation_hold_after_min}",
        "",
        "[tables]",
        "# seats_per_table, table_count",
    ]
    lines.extend(f"{table.seats},{table.count}" for table in scenario.tables)
    lines.extend(
        [
            "",
            "[arrivals]",
            "# group_id, arrival_time, group_size, dining_duration, patience, is_reservation, scheduled_time",
        ]
    )
    lines.extend(
        (
            f"{arrival.group_id},{arrival.arrival_time},{arrival.group_size},"
            f"{arrival.dining_duration},{'' if arrival.patience_override is None else arrival.patience_override},"
            f"{str(arrival.is_reservation).lower()},"
            f"{'' if arrival.scheduled_time is None else arrival.scheduled_time}"
        )
        for arrival in scenario.arrivals
    )
    lines.extend(
        [
            "",
            "[seed]",
            f"value={seed['value']}",
            f"generated={seed['generated']}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
