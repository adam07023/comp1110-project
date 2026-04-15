from __future__ import annotations

from domain.models import Scenario


def seed_metadata(scenario: Scenario) -> dict[str, str]:
    return {
        "value": "" if scenario.seed is None else str(scenario.seed),
        "generated": "true" if scenario.generated else "false",
    }
