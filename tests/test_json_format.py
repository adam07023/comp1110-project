import tempfile
import unittest
from pathlib import Path

from domain.models import GroupArrival, Scenario, TableInventory
from fileio.json_scenario_io import load_scenario_json, write_scenario_json


class JsonFormatTests(unittest.TestCase):
    def test_scenario_json_round_trip(self) -> None:
        scenario = Scenario(
            business_model_name="custom_demo",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=3)],
            arrivals=[
                GroupArrival(
                    group_id="G1",
                    arrival_time=1,
                    group_size=2,
                    dining_duration=10,
                    patience_override=7,
                )
            ],
            patience_threshold_mean=11.0,
            patience_threshold_sd=3.0,
            seed=12,
            generated=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "scenario.json"
            write_scenario_json(target, scenario)
            loaded = load_scenario_json(target)

        self.assertEqual(loaded.business_model_name, scenario.business_model_name)
        self.assertEqual(loaded.queue_type, scenario.queue_type)
        self.assertEqual(loaded.strategy_name, scenario.strategy_name)
        self.assertEqual(loaded.tables, scenario.tables)
        self.assertEqual(loaded.arrivals, scenario.arrivals)
        self.assertEqual(loaded.patience_threshold_mean, scenario.patience_threshold_mean)
        self.assertEqual(loaded.patience_threshold_sd, scenario.patience_threshold_sd)
        self.assertEqual(loaded.seed, scenario.seed)
        self.assertEqual(loaded.generated, scenario.generated)
