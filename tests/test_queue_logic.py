import unittest

from gui.queue_logic import MAX_QUEUE_LENGTH, QueueRowInput, sample_arrival_count, validate_queue_rows
from presets.builtins import get_builtin_models


class QueueLogicTests(unittest.TestCase):
    def test_validate_queue_rows_enforces_unique_arrival(self) -> None:
        model = get_builtin_models()["fast_food"]
        with self.assertRaises(ValueError):
            validate_queue_rows(
                [
                    QueueRowInput(arrival_time=1, group_size=2, dining_duration=12),
                    QueueRowInput(arrival_time=1, group_size=2, dining_duration=13),
                ],
                model,
            )

    def test_validate_queue_rows_sorts_and_preserves_patience(self) -> None:
        model = get_builtin_models()["fast_food"]
        arrivals = validate_queue_rows(
            [
                QueueRowInput(arrival_time=4, group_size=2, dining_duration=12, patience_override=7),
                QueueRowInput(arrival_time=2, group_size=1, dining_duration=10, patience_override=None),
            ],
            model,
        )
        self.assertEqual([row.arrival_time for row in arrivals], [2, 4])
        self.assertEqual(arrivals[1].patience_override, 7)

    def test_sample_arrival_count_is_bounded(self) -> None:
        class DummyRng:
            def gauss(self, _mean, _sd):
                return 1000

        sampled = sample_arrival_count("fast_food", DummyRng())
        self.assertEqual(sampled, MAX_QUEUE_LENGTH)
