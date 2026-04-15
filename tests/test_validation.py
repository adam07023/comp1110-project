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
