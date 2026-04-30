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
        self.assertEqual(result.statistics.service_level_threshold, 10)
        self.assertEqual(result.statistics.service_level_rate, 1.0)

    def test_engine_groups_leave_when_patience_expires(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[
                GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=20),
                GroupArrival(group_id="G2", arrival_time=1, group_size=2, dining_duration=5),
            ],
            patience_threshold_mean=5,
            patience_threshold_sd=0,
            seed=1,
        )

        result = run_simulation(scenario)

        self.assertEqual(result.statistics.served_groups, 1)
        self.assertEqual(result.statistics.rejected_groups, 1)
        self.assertEqual(result.rejected[0].reason, "left_due_to_patience")
        self.assertTrue(any(event.event_type == "abandonment" for event in result.events))

    def test_engine_tracks_ordering_wait(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[
                GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=10),
                GroupArrival(group_id="G2", arrival_time=1, group_size=2, dining_duration=5),
            ],
            servers=1,
            counter_order_time_min=5,
            counter_order_time_max=5,
            counter_order_time_mean=5,
            counter_order_time_sd=0,
        )

        result = run_simulation(scenario)

        self.assertEqual(result.statistics.served_groups, 2)
        self.assertEqual(result.statistics.average_ordering_wait_time, 2.0)
        self.assertTrue(any(event.event_type == "order_start" for event in result.events))
        self.assertTrue(any(event.event_type == "order_complete" for event in result.events))

    def test_server_capacity_allows_parallel_ordering(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=3)],
            arrivals=[
                GroupArrival(group_id="G1", arrival_time=0, group_size=2, dining_duration=5),
                GroupArrival(group_id="G2", arrival_time=0, group_size=2, dining_duration=5),
                GroupArrival(group_id="G3", arrival_time=0, group_size=2, dining_duration=5),
            ],
            servers=2,
            counter_order_time_min=5,
            counter_order_time_max=5,
            counter_order_time_mean=5,
            counter_order_time_sd=0,
        )

        result = run_simulation(scenario)

        order_starts_at_zero = [
            event for event in result.events
            if event.event_type == "order_start" and event.timestamp == 0
        ]
        self.assertEqual(len(order_starts_at_zero), 2)

    def test_engine_records_abandonment_stage(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[
                GroupArrival(
                    group_id="G1",
                    arrival_time=0,
                    group_size=2,
                    dining_duration=10,
                    patience_override=50,
                ),
                GroupArrival(
                    group_id="G2",
                    arrival_time=1,
                    group_size=2,
                    dining_duration=5,
                    patience_override=3,
                ),
            ],
            servers=1,
            counter_order_time_min=10,
            counter_order_time_max=10,
            counter_order_time_mean=10,
            counter_order_time_sd=0,
        )

        result = run_simulation(scenario)

        self.assertEqual(result.statistics.abandoned_at_ordering, 1)
        self.assertEqual(result.rejected[0].stage, "ordering")

    def test_reservations_skip_ordering_stage(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="single_queue",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=2, count=1)],
            arrivals=[
                GroupArrival(
                    group_id="R1",
                    arrival_time=3,
                    group_size=2,
                    dining_duration=10,
                    is_reservation=True,
                    scheduled_time=3,
                )
            ],
            servers=1,
            counter_order_time_min=10,
            counter_order_time_max=10,
            counter_order_time_mean=10,
            counter_order_time_sd=0,
            reservation_policy="hybrid_allocation",
            reserved_table_percent=1.0,
            reservation_hold_before_min=3,
            reservation_hold_after_min=3,
        )

        result = run_simulation(scenario)

        self.assertEqual(result.statistics.reservation_groups_served, 1)
        self.assertEqual(result.seated_groups[0].order_start_time, None)
        self.assertEqual(result.seated_groups[0].seated_time, 3)

    def test_food_truck_uses_tables_as_service_slots_without_ordering(self) -> None:
        scenario = Scenario(
            business_model_name="food_truck",
            queue_type="single_queue",
            strategy_name="strict_fifo_fit",
            tables=[TableInventory(seats=1, count=2)],
            arrivals=[
                GroupArrival(group_id="G1", arrival_time=0, group_size=1, dining_duration=5),
                GroupArrival(group_id="G2", arrival_time=0, group_size=1, dining_duration=5),
                GroupArrival(group_id="G3", arrival_time=0, group_size=1, dining_duration=5),
            ],
            servers=0,
            counter_order_time_min=0,
            counter_order_time_max=0,
            counter_order_time_mean=0,
            counter_order_time_sd=0,
        )

        result = run_simulation(scenario)

        self.assertFalse(any(event.event_type == "order_start" for event in result.events))
        self.assertFalse(any(event.event_type == "order_complete" for event in result.events))
        self.assertEqual(result.statistics.served_groups, 3)
        self.assertEqual(
            sorted(seated.seated_time for seated in result.seated_groups),
            [0, 0, 5],
        )

    def test_group_size_queue_reports_coarse_queue_lengths(self) -> None:
        scenario = Scenario(
            business_model_name="test",
            queue_type="queue_by_group_size",
            strategy_name="fifo_fit",
            tables=[TableInventory(seats=6, count=1)],
            arrivals=[
                GroupArrival(group_id="G1", arrival_time=0, group_size=1, dining_duration=10),
                GroupArrival(group_id="G2", arrival_time=0, group_size=3, dining_duration=10),
                GroupArrival(group_id="G3", arrival_time=0, group_size=5, dining_duration=10),
            ],
            servers=3,
            counter_order_time_min=0,
            counter_order_time_max=0,
            counter_order_time_mean=0,
            counter_order_time_sd=0,
        )

        result = run_simulation(scenario)

        self.assertEqual(result.statistics.max_queue_length_by_queue["1-2"], 0)
        self.assertEqual(result.statistics.max_queue_length_by_queue["3-4"], 1)
        self.assertEqual(result.statistics.max_queue_length_by_queue["5+"], 1)
