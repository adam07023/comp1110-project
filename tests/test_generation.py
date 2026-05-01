import unittest

from generation.randomizer import generate_random_scenario
from main import cli_generate_scenario
from presets.builtins import get_builtin_models


class GenerationTests(unittest.TestCase):
    def test_random_generation_is_seeded(self) -> None:
        model = get_builtin_models()["fast_food"]
        first = generate_random_scenario(model, seed=7, arrival_count=5, duration=60)
        second = generate_random_scenario(model, seed=7, arrival_count=5, duration=60)

        self.assertEqual(first.arrivals, second.arrivals)
        self.assertEqual(first.patience_threshold_mean, model.patience_threshold_mean)
        self.assertEqual(first.patience_threshold_sd, model.patience_threshold_sd)

    def test_random_generation_populates_patience_override(self) -> None:
        model = get_builtin_models()["cafe"]
        scenario = generate_random_scenario(model, seed=13, arrival_count=6, duration=45)

        self.assertTrue(all(arrival.patience_override is not None for arrival in scenario.arrivals))
        self.assertTrue(all(arrival.patience_override >= 1 for arrival in scenario.arrivals))

    def test_cli_generation_accepts_custom_business_model(self) -> None:
        model = get_builtin_models()["cafe"]
        custom_model = model.__class__(
            name="custom_cafe",
            queue_type=model.queue_type,
            strategy_name=model.strategy_name,
            tables=model.tables,
            generator_profile=model.generator_profile,
            patience_threshold_mean=model.patience_threshold_mean,
            patience_threshold_sd=model.patience_threshold_sd,
            notes=model.notes,
        )

        scenario = cli_generate_scenario(
            business_model=custom_model,
            seed=5,
            arrival_count=3,
            duration=20,
        )

        self.assertEqual(scenario.business_model_name, "custom_cafe")
        self.assertEqual(len(scenario.arrivals), 3)

    def test_generation_carries_ordering_resource_configuration(self) -> None:
        model = get_builtin_models()["fast_food"]
        scenario = generate_random_scenario(model, seed=21, arrival_count=3, duration=20)

        self.assertEqual(scenario.counters, model.counters)
        self.assertEqual(scenario.kiosks, model.kiosks)
        self.assertEqual(scenario.kiosk_usage_percent, model.kiosk_usage_percent)
        self.assertEqual(scenario.counter_order_time_mean, model.counter_order_time_mean)
        self.assertEqual(scenario.kiosk_order_time_mean, model.kiosk_order_time_mean)

    def test_generated_arrivals_are_sorted_by_arrival_time(self) -> None:
        model = get_builtin_models()["fast_food"]
        scenario = generate_random_scenario(model, seed=31, arrival_count=20, duration=120)

        arrival_times = [arrival.arrival_time for arrival in scenario.arrivals]
        self.assertEqual(arrival_times, sorted(arrival_times))

    def test_fine_dining_arrivals_cluster_later_than_fast_food(self) -> None:
        models = get_builtin_models()
        fast_food = generate_random_scenario(models["fast_food"], seed=44, arrival_count=80, duration=120)
        fine_dining = generate_random_scenario(models["fine_dining"], seed=44, arrival_count=80, duration=120)

        fast_average = sum(arrival.arrival_time for arrival in fast_food.arrivals) / len(fast_food.arrivals)
        fine_average = sum(arrival.arrival_time for arrival in fine_dining.arrivals) / len(fine_dining.arrivals)
        self.assertGreater(fine_average, fast_average)
