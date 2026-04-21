from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

from domain.business_model import BusinessModel
from domain.models import GroupArrival, Scenario, SimulationResult
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


def get_model(model_name: str) -> BusinessModel:
    """Get a business model by name. Raises ValueError if not found."""
    models = get_builtin_models()
    if model_name not in models:
        available = ", ".join(sorted(models))
        raise ValueError(f"Unknown model '{model_name}'. Available models: {available}")
    return models[model_name]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restaurant queue simulation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-models", help="List built-in business models")

    write_example = subparsers.add_parser(
        "write-example", help="Write a preset-based example scenario"
    )
    write_example.add_argument("--model", required=True)
    write_example.add_argument("--output", required=True)

    generate = subparsers.add_parser(
        "generate", help="Generate a random scenario from a built-in model"
    )
    generate.add_argument("--model", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--arrival-count", type=int, required=True)
    generate.add_argument("--duration", type=int, required=True)

    run = subparsers.add_parser("run", help="Run a simulation from a scenario file")
    run.add_argument("--scenario", required=True)
    run.add_argument("--output")

    subparsers.add_parser("gui", help="Launch the PyQt GUI")

    return parser


def command_list_models() -> int:
    for model in get_builtin_models().values():
        print(
            f"{model.name}: queue={model.queue_type}, strategy={model.strategy_name}, "
            f"tables={[(table.seats, table.count) for table in model.tables]}, "
            f"patience=(mean={model.patience_threshold_mean}, sd={model.patience_threshold_sd})"
        )
    return 0


def command_write_example(model_name: str, output: str) -> int:
    model = get_model(model_name)
    scenario = generate_random_scenario(
        business_model=model,
        seed=17,
        arrival_count=12,
        duration=120,
        generated=False,
    )
    write_scenario_file(Path(output), scenario)
    print(f"Wrote example scenario to {output}")
    return 0


def command_generate(model_name: str, output: str, seed: int, arrival_count: int, duration: int) -> int:
    model = get_model(model_name)
    scenario = generate_random_scenario(
        business_model=model,
        seed=seed,
        arrival_count=arrival_count,
        duration=duration,
        generated=True,
    )
    write_scenario_file(Path(output), scenario)
    print(f"Wrote generated scenario to {output}")
    return 0


def command_run(scenario_path: str, output: str | None) -> int:
    scenario = load_scenario(Path(scenario_path))
    result = run_simulation(scenario)

    if output:
        write_result_file(Path(output), result)
        print(f"Wrote simulation result to {output}")
    else:
        print(result.statistics.to_pretty_text())
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
    return load_scenario(Path(scenario_path))


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

        normalized.append(
            GroupArrival(
                group_id=f"G{index}",
                arrival_time=row.arrival_time,
                group_size=row.group_size,
                dining_duration=row.dining_duration,
                patience_override=row.patience_override,
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
        if args.command == "gui":
            return command_gui()
    except ValueError as error:
        parser.exit(status=2, message=f"error: {error}\n")

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
