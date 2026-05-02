import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from main import build_parser, command_generate, main


class CliTests(unittest.TestCase):
    def test_gui_command_is_available(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["gui"])
        self.assertEqual(args.command, "gui")

    def test_generate_rejects_non_positive_arrival_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "arrival-count"):
            command_generate("cafe", "/tmp/cli_test_unused.txt", 1, 0, 10)

    def test_generate_rejects_non_positive_duration(self) -> None:
        with self.assertRaisesRegex(ValueError, "duration"):
            command_generate("cafe", "/tmp/cli_test_unused.txt", 1, 5, 0)

    def test_main_reports_missing_scenario_without_traceback(self) -> None:
        missing = Path(__file__).resolve().parent / "nonexistent_scenario_12345.txt"
        stderr = io.StringIO()
        with mock.patch("sys.argv", ["main.py", "run", "--scenario", str(missing)]):
            with redirect_stderr(stderr):
                exit_code = main()
        self.assertEqual(exit_code, 2)
        self.assertIn("error:", stderr.getvalue())

    def test_epilog_mentions_analyze_config_path(self) -> None:
        parser = build_parser()
        self.assertIn("suite_analysis/scenario_suite.json", parser.epilog or "")
