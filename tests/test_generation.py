import unittest

from generation.randomizer import generate_random_scenario
from presets.builtins import get_builtin_models


class GenerationTests(unittest.TestCase):
    def test_random_generation_is_seeded(self) -> None:
        model = get_builtin_models()["fast_food"]
        first = generate_random_scenario(model, seed=7, arrival_count=5, duration=60)
        second = generate_random_scenario(model, seed=7, arrival_count=5, duration=60)

        self.assertEqual(first.arrivals, second.arrivals)
        self.assertEqual(first.patience_threshold_mean, model.patience_threshold_mean)
        self.assertEqual(first.patience_threshold_sd, model.patience_threshold_sd)
