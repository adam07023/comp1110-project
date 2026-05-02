from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from suite_analysis.config import load_analysis_config
from suite_analysis.report_writer import write_analysis_reports
from suite_analysis.runner import run_analysis_suite
from domain.business_model import BusinessModel
from domain.models import GroupArrival, Scenario, SimulationResult
from fileio.json_scenario_io import load_scenario_json
from fileio.result_writer import write_result_file
from fileio.scenario_loader import load_scenario
from fileio.scenario_writer import write_scenario_file
from generation.randomizer import generate_random_scenario
from presets.builtins import get_builtin_models
from simulation.engine import run_simulation

MAX_QUEUE_LENGTH = 99

ARRIVAL_COUNT_DISTRIBUTIONS: dict[str, tuple[float, float]] = {
    "fast_food": (26.0, 6.0),
    "fine_dining": (14.0, 4.0),
    "casual_dining": (34.0, 8.0),
    "cafe": (22.0, 5.0),
    "food_truck": (40.0, 10.0),
}


@dataclass(frozen=True)
class QueueRowInput:
    arrival_time: int
    group_size: int
    dining_duration: int
    patience_override: int | None = None
    is_reservation: bool = False
    scheduled_time: int | None = None


def get_model(model_name: str) -> BusinessModel:
    """Get a business model by name. Raises ValueError if not found."""
    models = get_builtin_models()
    if model_name not in models:
        available = ", ".join(sorted(models))
        raise ValueError(f"Unknown model '{model_name}'. Available models: {available}")
    return models[model_name]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Restaurant queue discrete-event simulator: run scenarios, generate queues, "
            "and batch experiments from a JSON suite (suite_analysis)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s list-models\n"
            "  %(prog)s run --scenario examples/fast_food_sample.txt\n"
            "  %(prog)s analyze --config suite_analysis/scenario_suite.json "
            "--output-dir suite_analysis/output\n"
            "\n"
            "Use .txt or .json scenario paths with run; see README.md."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-models", help="List built-in business models and key parameters")

    write_example = subparsers.add_parser(
        "write-example", help="Write a preset-based example scenario (.txt)"
    )
    write_example.add_argument("--model", required=True, help="Built-in model name")
    write_example.add_argument(
        "--output", required=True, metavar="PATH", help="Output scenario path (.txt)"
    )

    generate = subparsers.add_parser(
        "generate", help="Generate a random scenario from a built-in model (.txt)"
    )
    generate.add_argument("--model", required=True, help="Built-in model name")
    generate.add_argument(
        "--output", required=True, metavar="PATH", help="Output scenario path (.txt)"
    )
    generate.add_argument("--seed", type=int, required=True, help="RNG seed for reproducibility")
    generate.add_argument(
        "--arrival-count", type=int, required=True, metavar="N", help="Number of arrival groups"
    )
    generate.add_argument(
        "--duration", type=int, required=True, metavar="MIN", help="Simulation horizon (minutes)"
    )

    run = subparsers.add_parser(
        "run", help="Run one simulation from a scenario file (.txt or .json)"
    )
    run.add_argument(
        "--scenario", required=True, metavar="PATH", help="Path to scenario file"
    )
    run.add_argument(
        "--output",
        metavar="PATH",
        help="Write full result report to this path (default: print summary statistics)",
    )

    analyze = subparsers.add_parser(
        "analyze",
        help=(
            "Run all experiments in a JSON suite (replicated seeds, CSV/Markdown reports; "
            "see suite_analysis/scenario_suite.json)"
        ),
    )
    analyze.add_argument(
        "--config",
        required=True,
        metavar="PATH",
        help="Experiment suite JSON (e.g. suite_analysis/scenario_suite.json)",
    )
    analyze.add_argument(
        "--output-dir",
        required=True,
        metavar="DIR",
        help="Directory for analysis_report.md, aggregate_metrics.*, run artifacts",
    )
    analyze.add_argument(
        "--seeds",
        metavar="S1,S2,...",
        help="Override default seeds from the suite (comma-separated integers)",
    )
    analyze.add_argument(
        "--strict-expectations",
        action="store_true",
        help="Exit with error if a run's metric expectations are not met",
    )
    analyze.add_argument(
        "--write-scenarios",
        action="store_true",
        help="Also write generated scenario JSON next to each run's result .txt",
    )

    subparsers.add_parser("gui", help="Launch the PyQt6 GUI (requires PyQt6)")

    return parser


def command_list_models() -> int:
    for model in get_builtin_models().values():
        tables = [(table.seats, table.count) for table in model.tables]
        if model.reservation_policy != "none":
            res_info = (
                f"{model.reservation_policy} "
                f"(reserved_table_percent={model.reserved_table_percent})"
            )
        else:
            res_info = "none"
        print(
            f"{model.name}: queue={model.queue_type} strategy={model.strategy_name} "
            f"tables={tables} "
            f"counters={model.counters} kiosks={model.kiosks} "
            f"kiosk_usage_percent={model.kiosk_usage_percent} "
            f"patience_mean={model.patience_threshold_mean} patience_sd={model.patience_threshold_sd} "
            f"arrival_pattern={model.arrival_pattern} reservations={res_info}"
        )
    return 0


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def command_write_example(model_name: str, output: str) -> int:
    model = get_model(model_name)
    scenario = generate_random_scenario(
        business_model=model,
        seed=17,
        arrival_count=12,
        duration=120,
        generated=False,
    )
    out = Path(output)
    _ensure_parent_dir(out)
    write_scenario_file(out, scenario)
    print(f"Wrote example scenario to {out.resolve()}")
    return 0


def command_generate(model_name: str, output: str, seed: int, arrival_count: int, duration: int) -> int:
    if arrival_count <= 0:
        raise ValueError("--arrival-count must be a positive integer")
    if duration <= 0:
        raise ValueError("--duration must be a positive integer")
    model = get_model(model_name)
    scenario = generate_random_scenario(
        business_model=model,
        seed=seed,
        arrival_count=arrival_count,
        duration=duration,
        generated=True,
    )
    out = Path(output)
    _ensure_parent_dir(out)
    write_scenario_file(out, scenario)
    print(f"Wrote generated scenario to {out.resolve()} ({len(scenario.arrivals)} arrivals)")
    return 0


def command_run(scenario_path: str, output: str | None) -> int:
    path = Path(scenario_path)
    scenario = _load_scenario_path(path)
    result = run_simulation(scenario)

    if output:
        out = Path(output)
        _ensure_parent_dir(out)
        write_result_file(out, result)
        print(f"Wrote simulation result to {out.resolve()}")
    else:
        print(
            f"scenario={path.resolve()} "
            f"model={scenario.business_model_name} "
            f"queue={scenario.queue_type} "
            f"strategy={scenario.strategy_name}"
        )
        print()
        print(result.statistics.to_pretty_text())
    return 0


def _load_scenario_path(path: Path) -> Scenario:
    if path.suffix.lower() == ".json":
        return load_scenario_json(path)
    return load_scenario(path)


def command_analyze(
    config_path: str,
    output_dir: str,
    seeds: str | None = None,
    strict_expectations: bool = False,
    write_scenarios: bool = False,
) -> int:
    suite = load_analysis_config(Path(config_path))
    if seeds:
        suite = suite.__class__(
            experiments=suite.experiments,
            default_seeds=[int(seed.strip()) for seed in seeds.split(",") if seed.strip()],
            default_arrival_count=suite.default_arrival_count,
            default_duration=suite.default_duration,
            output_title=suite.output_title,
        )
    target_dir = Path(output_dir)
    result = run_analysis_suite(
        suite,
        output_dir=target_dir,
        write_scenarios=write_scenarios,
        strict_expectations=strict_expectations,
    )
    write_analysis_reports(target_dir, result)
    resolved = target_dir.resolve()
    print(f"Wrote suite analysis to {resolved}:")
    for name in (
        "analysis_report.md",
        "aggregate_metrics.csv",
        "aggregate_metrics.json",
        "all_runs_raw_metrics.csv",
    ):
        print(f"  {name}")
    if strict_expectations:
        print("All metric expectations met.")
    return 0


def command_gui() -> int:
    try:
        from gui_main import main as gui_main
    except ModuleNotFoundError as error:
        raise ValueError(
            "PyQt GUI dependencies are not installed. Install PyQt6 to use the gui command."
        ) from error
    return gui_main()


# === Exportable core functions for programmatic use (CLI and GUI) ===


def cli_generate_scenario(
    model_name: str | None = None,
    seed: int = 0,
    arrival_count: int = 0,
    duration: int = 0,
    business_model: BusinessModel | None = None,
) -> Scenario:
    """Generate a random scenario from a business model."""
    model = business_model if business_model is not None else get_model(model_name or "")
    return generate_random_scenario(
        business_model=model,
        seed=seed,
        arrival_count=arrival_count,
        duration=duration,
        generated=True,
    )


def cli_write_example_scenario(model_name: str) -> Scenario:
    """Generate an example scenario from a built-in model."""
    model = get_model(model_name)
    return generate_random_scenario(
        business_model=model,
        seed=17,
        arrival_count=12,
        duration=120,
        generated=False,
    )


def cli_run_simulation(scenario: Scenario) -> SimulationResult:
    """Run a simulation from a scenario."""
    return run_simulation(scenario)


def cli_load_scenario(scenario_path: str) -> Scenario:
    """Load a scenario from a file."""
    return _load_scenario_path(Path(scenario_path))


def cli_save_scenario(scenario: Scenario, output_path: str) -> None:
    """Save a scenario to a file."""
    write_scenario_file(Path(output_path), scenario)


def cli_save_result(result: SimulationResult, output_path: str) -> None:
    """Save a simulation result to a file."""
    write_result_file(Path(output_path), result)


def cli_sample_arrival_count(model_name: str, rng: random.Random) -> int:
    """Sample a bounded arrival count for random queue generation."""
    mean, sd = ARRIVAL_COUNT_DISTRIBUTIONS.get(model_name, (20.0, 6.0))
    sampled = int(round(rng.gauss(mean, sd)))
    return min(MAX_QUEUE_LENGTH, max(1, sampled))


def cli_validate_queue_rows(rows: list[QueueRowInput], model: BusinessModel) -> list[GroupArrival]:
    """Validate editable GUI/CLI queue rows against a business model."""
    if len(rows) > MAX_QUEUE_LENGTH:
        raise ValueError(f"Queue length cannot exceed {MAX_QUEUE_LENGTH}")

    profile = model.generator_profile
    normalized: list[GroupArrival] = []

    for index, row in enumerate(rows, start=1):
        if row.arrival_time < 0:
            raise ValueError("Arrival time cannot be negative")

        if not (profile.min_group_size <= row.group_size <= profile.max_group_size):
            raise ValueError(
                f"Group size must be between {profile.min_group_size} and {profile.max_group_size}"
            )
        if not (profile.min_dining_duration <= row.dining_duration <= profile.max_dining_duration):
            raise ValueError(
                "Dining duration must be between "
                f"{profile.min_dining_duration} and {profile.max_dining_duration}"
            )
        if row.patience_override is not None and row.patience_override <= 0:
            raise ValueError("Patience value must be positive when provided")
        if row.is_reservation and row.scheduled_time is None:
            raise ValueError("Reservation rows must include a scheduled time")
        if row.scheduled_time is not None and row.scheduled_time < 0:
            raise ValueError("Scheduled time cannot be negative")

        normalized.append(
            GroupArrival(
                group_id=f"G{index}",
                arrival_time=row.arrival_time,
                group_size=row.group_size,
                dining_duration=row.dining_duration,
                patience_override=row.patience_override,
                is_reservation=row.is_reservation,
                scheduled_time=row.scheduled_time,
            )
        )

    normalized.sort(key=lambda row: (row.arrival_time, row.group_id))
    return normalized


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "list-models":
            return command_list_models()
        if args.command == "write-example":
            return command_write_example(args.model, args.output)
        if args.command == "generate":
            return command_generate(args.model, args.output, args.seed, args.arrival_count, args.duration)
        if args.command == "run":
            return command_run(args.scenario, args.output)
        if args.command == "analyze":
            return command_analyze(
                args.config,
                args.output_dir,
                args.seeds,
                args.strict_expectations,
                args.write_scenarios,
            )
        if args.command == "gui":
            return command_gui()
        parser.error(f"Unknown command: {args.command}")
    except (ValueError, FileNotFoundError, PermissionError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
