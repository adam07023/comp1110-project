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
        "[tables]",
        "# seats_per_table, table_count",
    ]
    lines.extend(f"{table.seats},{table.count}" for table in scenario.tables)
    lines.extend(
        [
            "",
            "[arrivals]",
            "# arrival_time, group_size, dining_duration",
        ]
    )
    lines.extend(
        f"{arrival.arrival_time},{arrival.group_size},{arrival.dining_duration}"
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
