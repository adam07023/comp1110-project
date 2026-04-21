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
