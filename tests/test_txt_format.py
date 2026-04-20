import tempfile
import unittest
from pathlib import Path

from domain.models import GroupArrival, Scenario, TableInventory
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
        self.assertEqual(loaded.arrivals, scenario.arrivals)

    def test_scenario_round_trip_preserves_group_ids_and_patience(self) -> None:
        scenario = Scenario(
            business_model_name="custom_demo",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=3)],
            arrivals=[
                GroupArrival(
                    group_id="VIP-A",
                    arrival_time=1,
                    group_size=2,
                    dining_duration=10,
                    patience_override=7,
                ),
                GroupArrival(
                    group_id="VIP-B",
                    arrival_time=1,
                    group_size=1,
                    dining_duration=8,
                    patience_override=4,
                ),
            ],
            patience_threshold_mean=11.0,
            patience_threshold_sd=3.0,
            seed=12,
            generated=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "scenario.txt"
            write_scenario_file(target, scenario)
            loaded = load_scenario(target)

        self.assertEqual(loaded.arrivals, scenario.arrivals)

    def test_loader_rejects_missing_required_queue_fields_with_value_error(self) -> None:
        scenario_text = "\n".join(
            [
                "[business_model]",
                "name=fast_food",
                "",
                "[queue]",
                "type=single_queue",
                "",
                "[tables]",
                "2,1",
                "",
                "[arrivals]",
                "0,2,10",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "invalid.txt"
            target.write_text(scenario_text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "queue strategy"):
                load_scenario(target)
