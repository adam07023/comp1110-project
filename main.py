from __future__ import annotations

import argparse
from pathlib import Path

from domain.business_model import BusinessModel
from domain.models import Scenario, SimulationResult
from fileio.result_writer import write_result_file
from fileio.scenario_loader import load_scenario
from fileio.scenario_writer import write_scenario_file
from generation.randomizer import generate_random_scenario
from presets.builtins import get_builtin_models
from simulation.engine import run_simulation


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
    model_name: str, seed: int, arrival_count: int, duration: int
) -> Scenario:
    """Generate a random scenario from a built-in model."""
    model = get_model(model_name)
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
