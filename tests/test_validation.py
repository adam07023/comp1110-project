import unittest

from domain.models import GroupArrival, Scenario, TableInventory
from generation.validators import validate_scenario


class ValidationTests(unittest.TestCase):
    def test_validation_rejects_negative_duration(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=-1)],
        )

        with self.assertRaises(ValueError):
            validate_scenario(scenario)

    def test_validation_rejects_non_positive_patience_mean(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=10)],
            patience_threshold_mean=0,
            patience_threshold_sd=1,
        )

        with self.assertRaises(ValueError):
            validate_scenario(scenario)

    def test_validation_rejects_missing_ordering_resources(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=10)],
            counters=0,
            kiosks=0,
        )

        with self.assertRaisesRegex(ValueError, "ordering resource"):
            validate_scenario(scenario)

    def test_validation_rejects_bad_kiosk_usage_percent(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=10)],
            counters=1,
            kiosk_usage_percent=1.5,
        )

        with self.assertRaisesRegex(ValueError, "Kiosk usage percent"):
            validate_scenario(scenario)

    def test_validation_requires_scheduled_time_for_reservation(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[
                GroupArrival(
                    group_id="R1",
                    arrival_time=0,
                    group_size=2,
                    dining_duration=10,
                    is_reservation=True,
                )
            ],
        )

        with self.assertRaisesRegex(ValueError, "scheduled time"):
            validate_scenario(scenario)
