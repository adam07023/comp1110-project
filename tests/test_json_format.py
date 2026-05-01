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
        self.assertEqual(loaded.counters, scenario.counters)
        self.assertEqual(loaded.kiosks, scenario.kiosks)

    def test_nested_business_model_json_loads_service_fields(self) -> None:
        payload = """
{
  "business_model": {
    "name": "casual_dining",
    "queue_type": "single_queue",
    "strategy": "fifo_fit",
    "tables": [{"seats": 2, "count": 1}],
    "servers": 2,
    "counter_order_time_min": 1,
    "counter_order_time_max": 3,
    "counter_order_time_mean": 2,
    "counter_order_time_sd": 0.5,
    "kiosks": 1,
    "reservation_policy": "hybrid_allocation",
    "reserved_table_percent": 1.0,
    "reservation_hold_before_min": 5,
    "reservation_hold_after_min": 5,
    "patience_threshold_mean": 24.0,
    "patience_threshold_sd": 8.0
  },
  "seed": 42,
  "arrivals": [
    {
      "arrival_time": 5,
      "group_size": 2,
      "dining_duration": 48,
      "patience": 30,
      "is_reservation": true,
      "scheduled_time": 5
    }
  ]
}
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "scenario.json"
            target.write_text(payload, encoding="utf-8")
            loaded = load_scenario_json(target)

        self.assertEqual(loaded.business_model_name, "casual_dining")
        self.assertEqual(loaded.counters, 2)
        self.assertEqual(loaded.kiosks, 1)
        self.assertEqual(loaded.servers, 3)
        self.assertEqual(loaded.kiosk_order_time_mean, loaded.counter_order_time_mean)
        self.assertEqual(loaded.reservation_policy, "hybrid_allocation")
        self.assertTrue(loaded.arrivals[0].is_reservation)
        self.assertEqual(loaded.arrivals[0].scheduled_time, 5)

    def test_bad_json_reports_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "bad.json"
            target.write_text("{not valid json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Invalid JSON syntax"):
                load_scenario_json(target)

    def test_json_must_be_an_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "bad.json"
            target.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must be an object"):
                load_scenario_json(target)
