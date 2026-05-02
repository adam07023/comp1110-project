import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def load_v2_runner():
    project_root = Path(__file__).resolve().parents[1]
    runner_path = project_root / "scenario_analysis" / "runner.py"
    spec = importlib.util.spec_from_file_location("scenario_analysis_v2_runner", runner_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScenarioAnalysisV2Tests(unittest.TestCase):
    def test_v2_configs_load_all_pairs(self) -> None:
        runner = load_v2_runner()

        configs = runner.load_pair_configs(runner.SCENARIO_DIR)
        pair_ids = {config["pair_id"] for config in configs}

        self.assertEqual(len(configs), 14)
        self.assertIn("S1", pair_ids)
        self.assertIn("S8", pair_ids)
        self.assertIn("F6", pair_ids)

    def test_oat_gate_detects_non_trivial_change(self) -> None:
        runner = load_v2_runner()
        raw_rows = [
            {"pair_id": "S1", "run_id": "A", "seed": 1, "average_wait_time": 10.0},
            {"pair_id": "S1", "run_id": "B", "seed": 1, "average_wait_time": 7.0},
            {"pair_id": "S1", "run_id": "A", "seed": 2, "average_wait_time": 11.0},
            {"pair_id": "S1", "run_id": "B", "seed": 2, "average_wait_time": 8.0},
            {"pair_id": "S1", "run_id": "A", "seed": 3, "average_wait_time": 9.0},
            {"pair_id": "S1", "run_id": "B", "seed": 3, "average_wait_time": 6.0},
        ]
        summaries = [{"pair_id": "S1"}]

        gate_rows = runner.build_oat_gate(summaries, raw_rows)

        self.assertTrue(gate_rows[0]["factor_passes_gate"])
        self.assertEqual(gate_rows[0]["passing_metric"], "average_wait_time")

    def test_factorial_interaction_calculates_gap(self) -> None:
        runner = load_v2_runner()
        configs = [{"pair_id": "F1", "interaction_metric": "average_wait_time"}]
        summaries = [
            {"pair_id": "F1", "run_id": "A", "average_wait_time_mean": 10.0},
            {"pair_id": "F1", "run_id": "B", "average_wait_time_mean": 8.0},
            {"pair_id": "F1", "run_id": "C", "average_wait_time_mean": 12.0},
            {"pair_id": "F1", "run_id": "D", "average_wait_time_mean": 7.0},
        ]

        rows = runner.build_factorial_interactions(configs, summaries)

        self.assertEqual(rows[0]["b_minus_a"], -2.0)
        self.assertEqual(rows[0]["d_minus_c"], -5.0)
        self.assertEqual(rows[0]["interaction_gap"], 3.0)

    def test_v2_runner_smoke_writes_outputs(self) -> None:
        runner = load_v2_runner()
        config = {
            "pair_id": "S1",
            "kind": "oat",
            "description": "Tiny smoke scenario.",
            "base_model": "casual_dining",
            "seeds": [42],
            "arrival_count": 4,
            "duration": 20,
            "runs": [
                {"run_id": "A", "overrides": {"strategy": "fifo_fit"}},
                {"run_id": "B", "overrides": {"strategy": "best_fit"}},
            ],
            "assertions": [{"metric": "average_wait_time", "direction": "B < A"}],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner.SCENARIO_DIR = root / "scenarios"
            runner.INPUT_DIR = root / "inputs"
            runner.OUTPUT_DIR = root / "outputs"
            runner.SUMMARY_DIR = root / "summaries"
            runner.INSIGHT_DIR = root / "insights"
            runner.SCENARIO_DIR.mkdir()
            (runner.SCENARIO_DIR / "S1_strategy_oat.json").write_text(
                json.dumps(config),
                encoding="utf-8",
            )

            exit_code = runner.main()

            self.assertEqual(exit_code, 0)
            self.assertTrue((runner.INPUT_DIR / "baseline_casual_dining_seed42.json").exists())
            self.assertTrue((runner.SUMMARY_DIR / "oat_decision_gate.csv").exists())
            self.assertTrue((runner.INSIGHT_DIR / "analysis_report.md").exists())


if __name__ == "__main__":
    unittest.main()
