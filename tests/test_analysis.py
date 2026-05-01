import json
import tempfile
import unittest
from pathlib import Path

from analysis.config import load_analysis_config
from analysis.runner import run_analysis_suite
from analysis.scenario_builder import build_scenario
from main import build_parser, command_analyze


def _tiny_config() -> dict[str, object]:
    return {
        "default_seeds": [1],
        "default_arrival_count": 4,
        "default_duration": 20,
        "experiments": [
            {
                "scenario_name": "tiny_counter_check",
                "base_model": "casual_dining",
                "baseline_overrides": {
                    "queue_type": "single_queue",
                    "strategy": "fifo_fit",
                    "arrival_pattern": "uniform",
                    "tables": [{"seats": 2, "count": 2}, {"seats": 4, "count": 1}],
                    "counters": 1,
                    "patience_threshold_mean": 20.0,
                },
                "runs": [
                    {
                        "name": "one_counter",
                        "parameter_overrides": {"counters": 1},
                    },
                    {
                        "name": "two_counters",
                        "parameter_overrides": {"counters": 2},
                        "expected_metrics_direction": {
                            "server_utilization_rate": "decrease"
                        },
                    },
                ],
            }
        ],
    }


class AnalysisConfigTests(unittest.TestCase):
    def test_load_analysis_config_accepts_valid_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "suite.json"
            path.write_text(json.dumps(_tiny_config()), encoding="utf-8")

            suite = load_analysis_config(path)

        self.assertEqual(len(suite.experiments), 1)
        self.assertEqual(suite.experiments[0].scenario_name, "tiny_counter_check")
        self.assertEqual(suite.experiments[0].runs[1].name, "two_counters")

    def test_load_analysis_config_rejects_bad_strategy(self) -> None:
        payload = _tiny_config()
        experiment = payload["experiments"][0]  # type: ignore[index]
        experiment["runs"][0]["parameter_overrides"]["strategy"] = "not_real"  # type: ignore[index]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "suite.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unknown strategy"):
                load_analysis_config(path)


class AnalysisScenarioBuilderTests(unittest.TestCase):
    def test_build_scenario_applies_baseline_and_run_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "suite.json"
            path.write_text(json.dumps(_tiny_config()), encoding="utf-8")
            suite = load_analysis_config(path)

        experiment = suite.experiments[0]
        scenario = build_scenario(
            experiment,
            experiment.runs[1],
            seed=1,
            default_arrival_count=suite.default_arrival_count,
            default_duration=suite.default_duration,
        )

        self.assertEqual(scenario.queue_type, "single_queue")
        self.assertEqual(scenario.strategy_name, "fifo_fit")
        self.assertEqual(scenario.counters, 2)
        self.assertEqual(len(scenario.arrivals), 4)
        self.assertEqual([(table.seats, table.count) for table in scenario.tables], [(2, 2), (4, 1)])


class AnalysisRunnerTests(unittest.TestCase):
    def test_run_analysis_suite_aggregates_metrics_and_expectations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "suite.json"
            path.write_text(json.dumps(_tiny_config()), encoding="utf-8")
            suite = load_analysis_config(path)

            result = run_analysis_suite(suite)

        experiment = result.experiments[0]
        self.assertEqual(len(experiment.run_records), 2)
        self.assertEqual(len(experiment.aggregate_records), 2)
        self.assertIn("served_groups", experiment.aggregate_records[0].metrics)
        self.assertIn(
            "server_utilization_rate",
            experiment.aggregate_records[1].expectation_results,
        )


class AnalysisCliTests(unittest.TestCase):
    def test_analyze_command_is_available(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "analyze",
                "--config",
                "analysis/scenario_suite.json",
                "--output-dir",
                "analysis/output",
            ]
        )

        self.assertEqual(args.command, "analyze")

    def test_command_analyze_writes_reports_and_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "suite.json"
            output_dir = root / "output"
            config_path.write_text(json.dumps(_tiny_config()), encoding="utf-8")

            exit_code = command_analyze(
                str(config_path),
                str(output_dir),
                seeds=None,
                strict_expectations=False,
                write_scenarios=True,
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "analysis_report.md").exists())
            self.assertTrue((output_dir / "aggregate_metrics.csv").exists())
            self.assertTrue(any(output_dir.rglob("*.json")))


if __name__ == "__main__":
    unittest.main()
