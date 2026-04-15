import unittest

from domain.models import GroupArrival, Table
from simulation.queue_manager import SingleQueueManager
from simulation.strategies import choose_seating


class StrategyTests(unittest.TestCase):
    def test_best_fit_prefers_tighter_match(self) -> None:
        queue = SingleQueueManager()
        queue.enqueue(GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=10))
        queue.enqueue(GroupArrival(group_id="G2", arrival_time=1, group_size=4, dining_duration=10))

        choice = choose_seating(
            "best_fit",
            queue,
            [Table(table_id="T1", seats=6), Table(table_id="T2", seats=4)],
        )

        self.assertIsNotNone(choice)
        assert choice is not None
        self.assertEqual(choice.entry.group.group_id, "G2")
        self.assertEqual(choice.table.table_id, "T2")

    def test_strict_fifo_does_not_skip_the_head_of_queue(self) -> None:
        queue = SingleQueueManager()
        queue.enqueue(GroupArrival(group_id="G1", arrival_time=0, group_size=4, dining_duration=10))
        queue.enqueue(GroupArrival(group_id="G2", arrival_time=1, group_size=2, dining_duration=10))

        choice = choose_seating(
            "strict_fifo_fit",
            queue,
            [Table(table_id="T1", seats=2)],
        )

        self.assertIsNone(choice)
