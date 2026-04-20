import unittest

from main import build_parser


class CliTests(unittest.TestCase):
    def test_gui_command_is_available(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["gui"])
        self.assertEqual(args.command, "gui")
