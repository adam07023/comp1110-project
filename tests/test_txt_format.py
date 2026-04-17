import tempfile
import unittest
from pathlib import Path

from fileio.scenario_loader import load_scenario
from fileio.scenario_writer import write_scenario_file
from generation.randomizer import generate_random_scenario
from presets.builtins import get_builtin_models


class TxtFormatTests(unittest.TestCase):
    def test_scenario_round_trip(self) -> None:
        scenario = generate_random_scenario(
            get_builtin_models()["cafe"],
            seed=10,
            arrival_count=4,
            duration=30,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "scenario.txt"
            write_scenario_file(target, scenario)
            loaded = load_scenario(target)

        self.assertEqual(loaded.business_model_name, scenario.business_model_name)
        self.assertEqual(loaded.queue_type, scenario.queue_type)
        self.assertEqual(loaded.strategy_name, scenario.strategy_name)
        self.assertEqual(loaded.patience_threshold_mean, scenario.patience_threshold_mean)
        self.assertEqual(loaded.patience_threshold_sd, scenario.patience_threshold_sd)
        self.assertEqual(loaded.tables, scenario.tables)
        self.assertEqual(
            [(a.arrival_time, a.group_size, a.dining_duration) for a in loaded.arrivals],
            [(a.arrival_time, a.group_size, a.dining_duration) for a in scenario.arrivals],
        )
