from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from analysis.config import AnalysisSuiteConfig
from analysis.scenario_builder import build_scenario
from domain.models import SimulationResult, SimulationStatistics
from fileio.json_scenario_io import write_scenario_json
from fileio.result_writer import write_result_file
from simulation.engine import run_simulation


@dataclass(frozen=True)
class AnalysisRunRecord:
    experiment_name: str
    run_name: str
    seed: int
    metrics: dict[str, float]
    result: SimulationResult
    scenario_path: str | None = None
    result_path: str | None = None


@dataclass(frozen=True)
class AnalysisAggregateRecord:
    experiment_name: str
    run_name: str
    description: str
    metrics: dict[str, float]
    expectation_results: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisExperimentResult:
    scenario_name: str
    description: str
    run_records: list[AnalysisRunRecord]
    aggregate_records: list[AnalysisAggregateRecord]


@dataclass(frozen=True)
class AnalysisSuiteResult:
    title: str
    experiments: list[AnalysisExperimentResult]
    strict_expectations: bool = False

    @property
    def all_expectations_passed(self) -> bool:
        return all(
            passed
            for experiment in self.experiments
            for aggregate in experiment.aggregate_records
            for passed in aggregate.expectation_results.values()
        )


def run_analysis_suite(
    suite: AnalysisSuiteConfig,
    output_dir: Path | None = None,
    write_scenarios: bool = False,
    strict_expectations: bool = False,
) -> AnalysisSuiteResult:
    experiments: list[AnalysisExperimentResult] = []
    for experiment in suite.experiments:
        seeds = experiment.seeds or suite.default_seeds
        run_records: list[AnalysisRunRecord] = []
        for seed in seeds:
            for run in experiment.runs:
                scenario = build_scenario(
                    experiment,
                    run,
                    seed=seed,
                    default_arrival_count=suite.default_arrival_count,
                    default_duration=suite.default_duration,
                )
                result = run_simulation(scenario)
                scenario_path = None
                result_path = None
                if output_dir is not None:
                    scenario_path, result_path = _write_run_artifacts(
                        output_dir,
                        experiment.scenario_name,
                        run.name,
                        seed,
                        result,
                        write_scenarios,
                    )
                run_records.append(
                    AnalysisRunRecord(
                        experiment_name=experiment.scenario_name,
                        run_name=run.name,
                        seed=seed,
                        metrics=_extract_metrics(result.statistics),
                        result=result,
                        scenario_path=scenario_path,
                        result_path=result_path,
                    )
                )

        aggregate_records = _aggregate_experiment(experiment.scenario_name, experiment.description, run_records)
        aggregate_records = _evaluate_expectations(experiment.runs, aggregate_records)
        experiments.append(
            AnalysisExperimentResult(
                scenario_name=experiment.scenario_name,
                description=experiment.description,
                run_records=run_records,
                aggregate_records=aggregate_records,
            )
        )

    suite_result = AnalysisSuiteResult(
        title=suite.output_title,
        experiments=experiments,
        strict_expectations=strict_expectations,
    )
    if strict_expectations and not suite_result.all_expectations_passed:
        raise ValueError("One or more analysis metric expectations failed")
    return suite_result


def _write_run_artifacts(
    output_dir: Path,
    experiment_name: str,
    run_name: str,
    seed: int,
    result: SimulationResult,
    write_scenarios: bool,
) -> tuple[str | None, str]:
    experiment_dir = output_dir / experiment_name
    result_dir = experiment_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{run_name}_seed_{seed}"
    scenario_path = None
    if write_scenarios:
        scenario_dir = experiment_dir / "scenarios"
        scenario_dir.mkdir(parents=True, exist_ok=True)
        target = scenario_dir / f"{safe_name}.json"
        write_scenario_json(target, result.scenario)
        scenario_path = str(target)

    result_target = result_dir / f"{safe_name}.txt"
    write_result_file(result_target, result)
    return scenario_path, str(result_target)


def _aggregate_experiment(
    experiment_name: str,
    description: str,
    records: list[AnalysisRunRecord],
) -> list[AnalysisAggregateRecord]:
    run_names = []
    for record in records:
        if record.run_name not in run_names:
            run_names.append(record.run_name)

    aggregates: list[AnalysisAggregateRecord] = []
    for run_name in run_names:
        rows = [record for record in records if record.run_name == run_name]
        metric_names = sorted({metric for row in rows for metric in row.metrics})
        aggregates.append(
            AnalysisAggregateRecord(
                experiment_name=experiment_name,
                run_name=run_name,
                description=description,
                metrics={
                    metric: mean(row.metrics[metric] for row in rows if metric in row.metrics)
                    for metric in metric_names
                },
            )
        )
    return aggregates


def _evaluate_expectations(
    runs,
    aggregates: list[AnalysisAggregateRecord],
) -> list[AnalysisAggregateRecord]:
    if not aggregates:
        return aggregates
    baseline = aggregates[0]
    expectation_by_run = {
        run.name: run.expected_metrics_direction
        for run in runs
    }
    evaluated = []
    for aggregate in aggregates:
        expectations = expectation_by_run.get(aggregate.run_name, {})
        results = {
            metric: _direction_passed(
                baseline.metrics.get(_metric_alias(metric)),
                aggregate.metrics.get(_metric_alias(metric)),
                direction,
            )
            for metric, direction in expectations.items()
        }
        evaluated.append(
            AnalysisAggregateRecord(
                experiment_name=aggregate.experiment_name,
                run_name=aggregate.run_name,
                description=aggregate.description,
                metrics=aggregate.metrics,
                expectation_results=results,
            )
        )
    return evaluated


def _direction_passed(
    baseline: float | None,
    actual: float | None,
    direction: str,
    tolerance: float = 1e-9,
) -> bool:
    if baseline is None or actual is None:
        return False
    if direction == "increase":
        return actual > baseline + tolerance
    if direction == "decrease":
        return actual < baseline - tolerance
    if direction == "no_change":
        return abs(actual - baseline) <= tolerance
    return False


def _metric_alias(metric: str) -> str:
    aliases = {
        "table_utilization": "table_utilization_rate",
        "server_utilization": "server_utilization_rate",
        "average_wait": "average_wait_time",
        "max_wait": "max_wait_time",
    }
    return aliases.get(metric, metric)


def _extract_metrics(statistics: SimulationStatistics) -> dict[str, float]:
    metrics: dict[str, float] = {
        "served_groups": float(statistics.served_groups),
        "rejected_groups": float(statistics.rejected_groups),
        "total_groups": float(statistics.total_groups),
        "average_wait_time": statistics.average_wait_time,
        "min_wait_time": float(statistics.min_wait_time or 0),
        "max_wait_time": float(statistics.max_wait_time or 0),
        "longest_queue_length": float(statistics.longest_queue_length),
        "shortest_queue_length": float(statistics.shortest_queue_length),
        "table_utilization_rate": statistics.table_utilization_rate,
        "simulation_end_time": float(statistics.simulation_end_time),
        "service_level_rate": statistics.service_level_rate,
        "average_ordering_wait_time": statistics.average_ordering_wait_time,
        "server_utilization_rate": statistics.server_utilization_rate,
        "abandoned_at_ordering": float(statistics.abandoned_at_ordering),
        "abandoned_at_seating": float(statistics.abandoned_at_seating),
        "reservation_groups_served": float(statistics.reservation_groups_served),
        "reservation_no_shows": float(statistics.reservation_no_shows),
        "reservation_tables_released": float(statistics.reservation_tables_released),
    }
    for group_size, value in statistics.average_wait_by_group_size.items():
        metrics[f"average_wait_group_size_{group_size}"] = value
    for group_size, value in statistics.average_ordering_wait_by_group_size.items():
        metrics[f"average_ordering_wait_group_size_{group_size}"] = value
    for queue_label, value in statistics.max_queue_length_by_queue.items():
        safe_label = queue_label.replace("+", "plus").replace("-", "_")
        metrics[f"max_queue_length_queue_{safe_label}"] = float(value)
    return metrics
