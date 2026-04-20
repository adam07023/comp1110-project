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
        "[tables]",
        "# seats_per_table, table_count",
    ]
    lines.extend(f"{table.seats},{table.count}" for table in scenario.tables)
    lines.extend(
        [
            "",
            "[arrivals]",
            "# group_id, arrival_time, group_size, dining_duration, patience_override",
        ]
    )
    lines.extend(
        (
            f"{arrival.group_id},{arrival.arrival_time},{arrival.group_size},"
            f"{arrival.dining_duration},{'' if arrival.patience_override is None else arrival.patience_override}"
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
