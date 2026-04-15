import unittest

from domain.models import GroupArrival, Scenario, TableInventory
from simulation.engine import run_simulation


class EngineTests(unittest.TestCase):
    def test_engine_rejects_oversized_group_and_records_it(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[GroupArrival(group_id="G1", arrival_time=0, group_size=3, dining_duration=10)],
        )

        result = run_simulation(scenario)

        self.assertEqual(result.statistics.rejected_groups, 1)
        self.assertEqual(result.rejected[0].reason, "group_exceeds_largest_table")
        self.assertTrue(any(event.event_type == "rejection" for event in result.events))

    def test_engine_tracks_wait_and_served_groups(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[
                GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=10),
                GroupArrival(group_id="G2", arrival_time=1, group_size=2, dining_duration=5),
            ],
        )

        result = run_simulation(scenario)

        self.assertEqual(result.statistics.served_groups, 2)
        self.assertEqual(result.statistics.average_wait_time, 4.5)
        self.assertEqual(result.statistics.max_wait_time, 9)
