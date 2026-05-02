from __future__ import annotations

import random
from html import escape
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from domain.business_model import BusinessModel, GeneratorProfile
from domain.models import GroupArrival, Scenario, TableInventory
from fileio.json_scenario_io import load_scenario_json, write_scenario_json
from main import (
    MAX_QUEUE_LENGTH,
    QueueRowInput,
    cli_generate_scenario,
    cli_run_simulation,
    cli_sample_arrival_count,
    cli_save_result,
    cli_validate_queue_rows,
)
from presets.builtins import get_builtin_models


def _friendly_model_name(model_name: str) -> str:
    return model_name.replace("_", " ").title()


def _model_summary(model: BusinessModel) -> str:
    summaries = {
        "fast_food": "Fast service, compact tables, and a steady flow of small parties.",
        "fine_dining": "Longer meals, larger parties, and more deliberate table matching.",
        "casual_dining": "A balanced room with mixed party sizes and moderate dining times.",
        "cafe": "Mostly small groups, shorter stays, and efficient use of compact seating.",
        "food_truck": "Single-order service with strict first-come, first-served progression.",
    }
    return summaries.get(model.name, model.notes or "Custom restaurant configuration.")


def _format_model_details(model: BusinessModel) -> str:
    profile = model.generator_profile
    table_text = ", ".join(f"{table.count} table(s) of {table.seats}" for table in model.tables)
    weight_text = ", ".join(
        f"{group_size} guest(s): {weight:.2f}" for group_size, weight in sorted(profile.group_size_weights.items())
    )
    rows = [
        ("Model", _friendly_model_name(model.name)),
        ("Queue Type", model.queue_type.replace("_", " ")),
        ("Seating Strategy", model.strategy_name.replace("_", " ")),
        ("Arrival Pattern", model.arrival_pattern.replace("_", " ")),
        ("Group Size Range", f"{profile.min_group_size} to {profile.max_group_size} guests"),
        (
            "Dining Duration Range",
            f"{profile.min_dining_duration} to {profile.max_dining_duration} minutes",
        ),
        (
            "Patience Settings",
            f"mean {model.patience_threshold_mean:.0f} minutes, "
            f"standard deviation {model.patience_threshold_sd:.0f} minutes",
        ),
        ("Counters", str(model.counters)),
        ("Kiosks", str(model.kiosks)),
        ("Kiosk Usage", f"{model.kiosk_usage_percent * 100:.0f}%"),
        ("Counter Order Time", f"{model.counter_order_time_min} to {model.counter_order_time_max} minutes"),
        ("Kiosk Order Time", f"{model.kiosk_order_time_min} to {model.kiosk_order_time_max} minutes"),
        ("Reservation Policy", model.reservation_policy.replace("_", " ")),
        ("Tables", table_text),
        ("Group-Size Weighting", weight_text),
    ]
    detail_rows = "".join(
        f"<p style='margin: 0 0 12px 0;'><b>{escape(label)}</b>: {escape(value)}</p>"
        for label, value in rows
    )
    return (
        "<div style='font-size: 14px; line-height: 1.35;'>"
        f"{detail_rows}"
        f"<p style='margin: 16px 0 0 0;'>{escape(_model_summary(model))}</p>"
        "</div>"
    )


def _format_stat_line(label: str, value: str) -> str:
    if label == "table_utilization_rate":
        return f"Table utilization: {float(value) * 100:.1f}%"

    if label == "service_level_rate":
        return f"Service level: {float(value) * 100:.1f}%"

    if label == "service_level_threshold":
        return f"Service level threshold: {value} minutes"

    if label == "simulation_end_time":
        return f"Simulation end time: {value} minutes"

    if label == "server_utilization_rate":
        return f"Ordering resource utilization: {float(value) * 100:.1f}%"

    if label.startswith("max_queue_length_queue_"):
        queue_label = label.removeprefix("max_queue_length_queue_").replace("_", "-").replace("plus", "+")
        return f"Maximum queue length ({queue_label}): {value}"

    if label.startswith("average_wait_group_size_"):
        group_size = label.rsplit("_", 1)[-1]
        return f"Average total wait for group size {group_size}: {value} minutes"

    if label.startswith("average_ordering_wait_group_size_"):
        group_size = label.rsplit("_", 1)[-1]
        return f"Average ordering wait for group size {group_size}: {value} minutes"

    label_map = {
        "served_groups": "Groups served",
        "rejected_groups": "Groups rejected",
        "total_groups": "Total groups",
        "average_wait_time": "Average wait time",
        "min_wait_time": "Minimum wait time",
        "max_wait_time": "Maximum wait time",
        "longest_queue_length": "Maximum queue length",
        "shortest_queue_length": "Minimum queue length",
        "average_ordering_wait_time": "Average ordering wait time",
        "abandoned_at_ordering": "Abandoned during ordering",
        "abandoned_at_seating": "Abandoned during seating",
        "reservation_groups_served": "Reservation groups served",
        "reservation_no_shows": "Reservation no-shows",
        "reservation_tables_released": "Reservation tables released",
    }
    friendly = label_map.get(label, label.replace("_", " ").capitalize())
    if "wait" in label:
        return f"{friendly}: {value} minutes"
    return f"{friendly}: {value}"


def _build_statistics_sections(result) -> dict[str, list[str]]:
    stat_lines: dict[str, str] = {}
    for raw_line in result.statistics.to_pretty_text().splitlines():
        if "=" not in raw_line:
            continue
        label, value = raw_line.split("=", 1)
        stat_lines[label] = _format_stat_line(label, value)

    sections: dict[str, list[str]] = {}

    def add_section(title: str, keys: list[str]) -> None:
        section_lines = [stat_lines[key] for key in keys if key in stat_lines]
        if not section_lines:
            return
        sections[title] = section_lines

    add_section(
        "Overview",
        ["total_groups", "served_groups", "rejected_groups", "simulation_end_time"],
    )
    add_section(
        "Wait Times",
        ["average_wait_time", "min_wait_time", "max_wait_time"],
    )
    add_section(
        "Queue And Capacity",
        [
            "longest_queue_length",
            "shortest_queue_length",
            "table_utilization_rate",
            "service_level_threshold",
            "service_level_rate",
        ],
    )
    add_section(
        "Queue Length By Queue",
        [key for key in sorted(stat_lines) if key.startswith("max_queue_length_queue_")],
    )
    add_section(
        "Ordering And Seating",
        [
            "average_ordering_wait_time",
            "server_utilization_rate",
            "abandoned_at_ordering",
            "abandoned_at_seating",
        ],
    )
    add_section(
        "Reservations",
        ["reservation_groups_served", "reservation_no_shows", "reservation_tables_released"],
    )
    add_section(
        "Total Wait Time By Group Size (arrival to seating)",
        [key for key in sorted(stat_lines) if key.startswith("average_wait_group_size_")],
    )
    add_section(
        "Ordering Wait By Group Size",
        [key for key in sorted(stat_lines) if key.startswith("average_ordering_wait_group_size_")],
    )
    return sections


def _format_statistics_column(sections: dict[str, list[str]], ordered_titles: list[str]) -> str:
    lines: list[str] = []
    for title in ordered_titles:
        section_lines = sections.get(title)
        if not section_lines:
            continue
        if lines:
            lines.append("")
        lines.append(title)
        lines.append("-" * len(title))
        lines.extend(section_lines)
    return "\n".join(lines)


def _format_scenario_text(scenario: Scenario) -> str:
    lines = [
        f"Model: {_friendly_model_name(scenario.business_model_name)}",
        f"Queue style: {scenario.queue_type.replace('_', ' ')}",
        f"Seating strategy: {scenario.strategy_name.replace('_', ' ')}",
        "Tables: " + ", ".join(f"{table.count} x {table.seats}-seat" for table in scenario.tables),
        f"Counters: {scenario.counters}",
        f"Kiosks: {scenario.kiosks}",
        f"Kiosk usage: {scenario.kiosk_usage_percent * 100:.0f}%",
        (
            "Counter order time: "
            f"{scenario.counter_order_time_min} to {scenario.counter_order_time_max} minutes"
        ),
        (
            "Kiosk order time: "
            f"{scenario.kiosk_order_time_min} to {scenario.kiosk_order_time_max} minutes"
        ),
        "",
        "Arrivals:",
    ]
    for row in scenario.arrivals:
        patience_text = (
            f"{row.patience_override} minutes" if row.patience_override is not None else "automatic"
        )
        reservation_text = (
            f", reservation at {row.scheduled_time} minutes" if row.is_reservation else ""
        )
        lines.append(
            f"- At {row.arrival_time} minutes: group of {row.group_size}, "
            f"dining for {row.dining_duration} minutes, patience {patience_text}{reservation_text}"
        )
    return "\n".join(lines)


def _parse_tables(raw: str) -> list[TableInventory]:
    tables: list[TableInventory] = []
    for token in [entry.strip() for entry in raw.split(",") if entry.strip()]:
        seats_text, count_text = token.split(":", 1)
        seats = int(seats_text.strip())
        count = int(count_text.strip())
        if seats <= 0 or count <= 0:
            raise ValueError("Table seats and counts must be positive")
        tables.append(TableInventory(seats=seats, count=count))
    if not tables:
        raise ValueError("At least one table row is required")
    return tables


def _parse_weights(raw: str, minimum: int, maximum: int) -> dict[int, float]:
    weights: dict[int, float] = {}
    for token in [entry.strip() for entry in raw.split(",") if entry.strip()]:
        size_text, weight_text = token.split(":", 1)
        size = int(size_text.strip())
        weight = float(weight_text.strip())
        if size < minimum or size > maximum:
            raise ValueError("Weight key outside min/max group size bounds")
        if weight <= 0:
            raise ValueError("Weights must be positive")
        weights[size] = weight
    if not weights:
        raise ValueError("At least one group-size weight is required")
    return weights


class CustomModelDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom Restaurant Parameters")
        self.setModal(True)
        self.resize(1050, 560)

        self.name_input = QLineEdit()
        self.min_group_input = QLineEdit("1")
        self.max_group_input = QLineEdit("4")
        self.min_dining_input = QLineEdit("10")
        self.max_dining_input = QLineEdit("60")
        self.dining_mean_input = QLineEdit("35")
        self.dining_sd_input = QLineEdit("10")
        self.patience_mean_input = QLineEdit("20")
        self.patience_sd_input = QLineEdit("6")
        self.queue_type_input = self._combo(["single_queue", "queue_by_group_size"])
        self.strategy_input = self._combo(
            [
                "fifo_fit",
                "best_fit",
                "smallest_table_fit",
                "strict_fifo_fit",
                "first_available",
                "exact_match",
            ]
        )
        self.arrival_pattern_input = self._combo(
            [
                "uniform",
                "left_skewed",
                "centered",
                "right_skewed",
            ]
        )
        self.tables_input = QLineEdit("2:4,4:4")
        self.weights_input = QLineEdit("1:0.3,2:0.3,3:0.2,4:0.2")
        self.counters_input = QLineEdit("1")
        self.kiosks_input = QLineEdit("0")
        self.kiosk_usage_input = QLineEdit("0")
        self.counter_min_input = QLineEdit("0")
        self.counter_max_input = QLineEdit("4")
        self.counter_mean_input = QLineEdit("2")
        self.counter_sd_input = QLineEdit("0.8")
        self.kiosk_min_input = QLineEdit("0")
        self.kiosk_max_input = QLineEdit("4")
        self.kiosk_mean_input = QLineEdit("2")
        self.kiosk_sd_input = QLineEdit("0.8")
        self.reservation_policy_input = self._combo(["none", "hybrid_allocation"])
        self.reserved_percent_input = QLineEdit("0")
        self.hold_before_input = QLineEdit("0")
        self.hold_after_input = QLineEdit("0")

        layout = QVBoxLayout(self)
        columns = QHBoxLayout()
        columns.setSpacing(18)

        profile_group, profile_form = self._group_form("Profile")
        profile_form.addRow("Model Name", self.name_input)
        profile_form.addRow("Queue Type", self.queue_type_input)
        profile_form.addRow("Strategy", self.strategy_input)
        profile_form.addRow("Arrival Pattern", self.arrival_pattern_input)
        profile_form.addRow("Tables (seats:count,...)", self.tables_input)
        profile_form.addRow("Group Weights (size:weight,...)", self.weights_input)
        columns.addWidget(profile_group)

        timing_group, timing_form = self._group_form("Timing")
        timing_form.addRow("Min Group Size", self.min_group_input)
        timing_form.addRow("Max Group Size", self.max_group_input)
        timing_form.addRow("Min Dining Duration", self.min_dining_input)
        timing_form.addRow("Max Dining Duration", self.max_dining_input)
        timing_form.addRow("Dining Duration Mean", self.dining_mean_input)
        timing_form.addRow("Dining Duration SD", self.dining_sd_input)
        timing_form.addRow("Patience Mean", self.patience_mean_input)
        timing_form.addRow("Patience SD", self.patience_sd_input)
        columns.addWidget(timing_group)

        service_group, service_form = self._group_form("Ordering And Reservations")
        service_form.addRow("Counter Number", self.counters_input)
        service_form.addRow("Kiosk Number", self.kiosks_input)
        service_form.addRow("Kiosk Usage Percent", self.kiosk_usage_input)
        service_form.addRow("Counter Time Min / Max", self._paired_inputs(self.counter_min_input, self.counter_max_input))
        service_form.addRow("Counter Time Mean / SD", self._paired_inputs(self.counter_mean_input, self.counter_sd_input))
        service_form.addRow("Kiosk Time Min / Max", self._paired_inputs(self.kiosk_min_input, self.kiosk_max_input))
        service_form.addRow("Kiosk Time Mean / SD", self._paired_inputs(self.kiosk_mean_input, self.kiosk_sd_input))
        service_form.addRow("Reservation Policy", self.reservation_policy_input)
        service_form.addRow("Reserved Table Percent", self.reserved_percent_input)
        service_form.addRow("Reservation Hold Before", self.hold_before_input)
        service_form.addRow("Reservation Hold After", self.hold_after_input)
        columns.addWidget(service_group)

        layout.addLayout(columns)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancel")
        save = QPushButton("Select")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _combo(self, values: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(values)
        longest_value = max(values, key=len)
        popup_width = combo.fontMetrics().horizontalAdvance(longest_value) + 48
        combo.setMinimumContentsLength(len(longest_value))
        combo.setMinimumWidth(popup_width)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.view().setMinimumWidth(popup_width)
        return combo

    def _group_form(self, title: str) -> tuple[QGroupBox, QFormLayout]:
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        return group, form

    def _paired_inputs(self, first: QLineEdit, second: QLineEdit) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(first)
        layout.addWidget(second)
        return container

    def build_model(self) -> BusinessModel:
        name = self.name_input.text().strip()
        if not name:
            raise ValueError("Model name is required")

        min_group = int(self.min_group_input.text())
        max_group = int(self.max_group_input.text())
        if min_group > max_group:
            raise ValueError("Min group size cannot exceed max group size")

        min_dining = int(self.min_dining_input.text())
        max_dining = int(self.max_dining_input.text())
        if min_dining > max_dining:
            raise ValueError("Min dining duration cannot exceed max dining duration")

        weights = _parse_weights(self.weights_input.text(), min_group, max_group)
        tables = _parse_tables(self.tables_input.text())
        patience_mean = float(self.patience_mean_input.text())
        patience_sd = float(self.patience_sd_input.text())
        if patience_mean <= 0 or patience_sd < 0:
            raise ValueError("Patience mean must be positive and SD cannot be negative")
        kiosk_usage_percent = float(self.kiosk_usage_input.text())
        if not 0 <= kiosk_usage_percent <= 100:
            raise ValueError("Kiosk usage percent must be between 0 and 100")

        return BusinessModel(
            name=name,
            queue_type=self.queue_type_input.currentText(),
            strategy_name=self.strategy_input.currentText(),
            tables=tables,
            generator_profile=GeneratorProfile(
                min_group_size=min_group,
                max_group_size=max_group,
                group_size_weights=weights,
                min_dining_duration=min_dining,
                max_dining_duration=max_dining,
                dining_duration_mean=float(self.dining_mean_input.text()),
                dining_duration_sd=float(self.dining_sd_input.text()),
            ),
            patience_threshold_mean=patience_mean,
            patience_threshold_sd=patience_sd,
            counters=int(self.counters_input.text()),
            kiosks=int(self.kiosks_input.text()),
            kiosk_usage_percent=kiosk_usage_percent / 100,
            counter_order_time_min=int(self.counter_min_input.text()),
            counter_order_time_max=int(self.counter_max_input.text()),
            counter_order_time_mean=float(self.counter_mean_input.text()),
            counter_order_time_sd=float(self.counter_sd_input.text()),
            kiosk_order_time_min=int(self.kiosk_min_input.text()),
            kiosk_order_time_max=int(self.kiosk_max_input.text()),
            kiosk_order_time_mean=float(self.kiosk_mean_input.text()),
            kiosk_order_time_sd=float(self.kiosk_sd_input.text()),
            reservation_policy=self.reservation_policy_input.currentText(),
            reserved_table_percent=float(self.reserved_percent_input.text()),
            reservation_hold_before_min=int(self.hold_before_input.text()),
            reservation_hold_after_min=int(self.hold_after_input.text()),
            arrival_pattern=self.arrival_pattern_input.currentText(),
            notes="Custom model created from GUI",
        )


@dataclass
class AppState:
    model: BusinessModel | None = None
    scenario: Scenario | None = None
    loaded_from_json: bool = False


class Layer1Widget(QWidget):
    def __init__(self, on_model_selected, on_scenario_loaded) -> None:
        super().__init__()
        self.on_model_selected = on_model_selected
        self.on_scenario_loaded = on_scenario_loaded
        self.models = get_builtin_models()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        layout.setSpacing(18)
        title = QLabel("Choose Restaurant Configuration")
        title.setProperty("title", True)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        layout.addSpacing(16)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(18)
        grid.setContentsMargins(24, 10, 24, 0)
        ordered = ["fast_food", "fine_dining", "casual_dining", "cafe", "food_truck"]
        for idx, key in enumerate(ordered):
            model = self.models[key]
            card = QWidget()
            card_wrapper = QVBoxLayout(card)
            card_wrapper.setContentsMargins(0, 0, 0, 0)
            card_wrapper.setSpacing(6)
            card_title = QLabel(_friendly_model_name(model.name))
            card_title.setProperty("cardTitle", True)
            card_wrapper.addWidget(card_title)
            card_box = QGroupBox()
            card_layout = QVBoxLayout(card_box)
            card_layout.setSpacing(12)
            info = QLabel(_model_summary(model))
            info.setWordWrap(True)
            card_layout.addWidget(info)
            view_btn = QPushButton("View Parameters")
            select_btn = QPushButton("Select Model")
            view_btn.clicked.connect(lambda _checked=False, selected=model: self._view_model(selected))
            select_btn.clicked.connect(lambda _checked=False, selected=model: self.on_model_selected(selected))
            card_layout.addWidget(view_btn)
            card_layout.addWidget(select_btn)
            card_wrapper.addWidget(card_box)
            grid.addWidget(card, idx // 3, idx % 3)

        custom_card = QWidget()
        custom_wrapper = QVBoxLayout(custom_card)
        custom_wrapper.setContentsMargins(0, 0, 0, 0)
        custom_wrapper.setSpacing(6)
        custom_title = QLabel("Customize Restaurant")
        custom_title.setProperty("cardTitle", True)
        custom_wrapper.addWidget(custom_title)
        custom_box = QGroupBox()
        custom_layout = QVBoxLayout(custom_box)
        custom_layout.setSpacing(12)
        custom_text = QLabel("Create a tailored restaurant setup with your own seating and timing rules.")
        custom_text.setWordWrap(True)
        custom_layout.addWidget(custom_text)
        custom_btn = QPushButton("Select")
        custom_btn.clicked.connect(self._customize)
        custom_layout.addWidget(custom_btn)
        custom_wrapper.addWidget(custom_box)
        grid.addWidget(custom_card, 1, 2)
        layout.addLayout(grid)
        layout.addStretch(1)

        load_row = QHBoxLayout()
        load_row.setContentsMargins(24, 4, 24, 0)
        load_btn = QPushButton("Load Scenario JSON")
        load_btn.clicked.connect(self._load_json)
        load_row.addWidget(load_btn)
        load_row.addStretch(1)
        layout.addLayout(load_row)

    def _view_model(self, model: BusinessModel) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Model Parameters")
        dialog.setModal(True)
        dialog.resize(760, 620)

        layout = QVBoxLayout(dialog)
        details = QTextBrowser(dialog)
        details.setOpenExternalLinks(False)
        details.setHtml(_format_model_details(model))
        layout.addWidget(details)

        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        actions.rejected.connect(dialog.reject)
        actions.accepted.connect(dialog.accept)
        layout.addWidget(actions)

        dialog.exec()

    def _customize(self) -> None:
        dialog = CustomModelDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            model = dialog.build_model()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid Custom Model", str(error))
            return
        self.on_model_selected(model)

    def _load_json(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON Files (*.json)")
        if not selected:
            return
        selected_path = Path(selected)
        if selected_path.suffix.lower() != ".json":
            QMessageBox.critical(
                self,
                "Bad Input",
                "Only .json files are supported. Please choose a JSON scenario file.",
            )
            return
        try:
            scenario = load_scenario_json(selected_path)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Bad Input",
                f"This JSON file could not be processed.\n\n{error}",
            )
            return
        self.on_scenario_loaded(scenario)


class Layer2Widget(QWidget):
    def __init__(self, on_run) -> None:
        super().__init__()
        self.on_run = on_run
        self.model: BusinessModel | None = None
        self.loaded_scenario: Scenario | None = None
        self._is_sorting = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        layout.setSpacing(18)
        header = QLabel("Build Queue")
        header.setProperty("title", True)
        header.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(header)
        layout.addSpacing(12)

        controls = QHBoxLayout()
        self.random_btn = QPushButton("Randomly Generate Queue")
        self.random_btn.clicked.connect(self._randomize)
        save_btn = QPushButton("Save Scenario JSON")
        save_btn.clicked.connect(self._save_json)
        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._add_row)
        remove_btn = QPushButton("- Remove")
        remove_btn.clicked.connect(self._remove_row)
        controls.addWidget(self.random_btn)
        controls.addWidget(save_btn)
        controls.addWidget(add_btn)
        controls.addWidget(remove_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [
                "Arrival Time (min)",
                "Group Size",
                "Dining Duration (min)",
                "Patience (min)",
                "Reservation",
                "Scheduled Time",
            ]
        )
        self.table.setColumnWidth(0, 200)  # Arrival Time
        self.table.setColumnWidth(1, 200)  # Group Size
        self.table.setColumnWidth(2, 200)  # Dining Duration
        self.table.setColumnWidth(3, 200)  # Patience
        self.table.setColumnWidth(4, 140)  # Reservation
        self.table.setColumnWidth(5, 160)  # Scheduled Time
        self.table.itemChanged.connect(self._sort_by_arrival)
        layout.addWidget(self.table)
        self.table.setFixedHeight(600)

        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)
        layout.addStretch(1)

    def set_context(self, model: BusinessModel, loaded_scenario: Scenario | None = None) -> None:
        self.model = model
        self.loaded_scenario = loaded_scenario
        self._populate_from_scenario(loaded_scenario.arrivals if loaded_scenario else [])

    def _populate_from_scenario(self, arrivals) -> None:
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            for arrival in arrivals:
                self._add_row(
                    arrival.arrival_time,
                    arrival.group_size,
                    arrival.dining_duration,
                    arrival.patience_override,
                    arrival.is_reservation,
                    arrival.scheduled_time,
                    arrival.group_id,
                )
        finally:
            self.table.blockSignals(False)
        self._sort_by_arrival()

    def _read_rows(self) -> list[QueueRowInput]:
        rows: list[QueueRowInput] = []
        for index in range(self.table.rowCount()):
            arrival_item = self.table.item(index, 0)
            group_item = self.table.item(index, 1)
            dining_item = self.table.item(index, 2)
            patience_item = self.table.item(index, 3)
            reservation_item = self.table.item(index, 4)
            scheduled_item = self.table.item(index, 5)

            if not arrival_item or not group_item or not dining_item:
                raise ValueError("Arrival, group size, and dining duration are required")

            patience_text = patience_item.text().strip() if patience_item else ""
            reservation_text = reservation_item.text().strip().lower() if reservation_item else ""
            scheduled_text = scheduled_item.text().strip() if scheduled_item else ""
            rows.append(
                QueueRowInput(
                    arrival_time=int(arrival_item.text()),
                    group_size=int(group_item.text()),
                    dining_duration=int(dining_item.text()),
                    patience_override=int(patience_text) if patience_text else None,
                    is_reservation=reservation_text in {"true", "yes", "y", "1"},
                    scheduled_time=int(scheduled_text) if scheduled_text else None,
                )
            )
        return rows

    def _build_scenario(self) -> Scenario:
        if not self.model:
            raise ValueError("No business model selected")

        source = self.loaded_scenario
        if source is not None:
            arrivals = self._read_arrivals_preserving_loaded_ids()
            return Scenario(
                business_model_name=source.business_model_name,
                queue_type=source.queue_type,
                strategy_name=source.strategy_name,
                tables=source.tables,
                arrivals=arrivals,
                patience_threshold_mean=source.patience_threshold_mean,
                patience_threshold_sd=source.patience_threshold_sd,
                seed=source.seed,
                generated=source.generated,
                counters=source.counters,
                kiosks=source.kiosks,
                kiosk_usage_percent=source.kiosk_usage_percent,
                counter_order_time_min=source.counter_order_time_min,
                counter_order_time_max=source.counter_order_time_max,
                counter_order_time_mean=source.counter_order_time_mean,
                counter_order_time_sd=source.counter_order_time_sd,
                kiosk_order_time_min=source.kiosk_order_time_min,
                kiosk_order_time_max=source.kiosk_order_time_max,
                kiosk_order_time_mean=source.kiosk_order_time_mean,
                kiosk_order_time_sd=source.kiosk_order_time_sd,
                reservation_policy=source.reservation_policy,
                reserved_table_percent=source.reserved_table_percent,
                reservation_hold_before_min=source.reservation_hold_before_min,
                reservation_hold_after_min=source.reservation_hold_after_min,
            )
        arrivals = cli_validate_queue_rows(self._read_rows(), self.model)
        return Scenario(
            business_model_name=self.model.name,
            queue_type=self.model.queue_type,
            strategy_name=self.model.strategy_name,
            tables=self.model.tables,
            arrivals=arrivals,
            patience_threshold_mean=self.model.patience_threshold_mean,
            patience_threshold_sd=self.model.patience_threshold_sd,
            seed=(self.loaded_scenario.seed if self.loaded_scenario else None),
            generated=(self.loaded_scenario.generated if self.loaded_scenario else False),
            counters=self.model.counters,
            kiosks=self.model.kiosks,
            kiosk_usage_percent=self.model.kiosk_usage_percent,
            counter_order_time_min=self.model.counter_order_time_min,
            counter_order_time_max=self.model.counter_order_time_max,
            counter_order_time_mean=self.model.counter_order_time_mean,
            counter_order_time_sd=self.model.counter_order_time_sd,
            kiosk_order_time_min=self.model.kiosk_order_time_min,
            kiosk_order_time_max=self.model.kiosk_order_time_max,
            kiosk_order_time_mean=self.model.kiosk_order_time_mean,
            kiosk_order_time_sd=self.model.kiosk_order_time_sd,
            reservation_policy=self.model.reservation_policy,
            reserved_table_percent=self.model.reserved_table_percent,
            reservation_hold_before_min=self.model.reservation_hold_before_min,
            reservation_hold_after_min=self.model.reservation_hold_after_min,
        )

    def _read_arrivals_preserving_loaded_ids(self) -> list[GroupArrival]:
        if not self.model:
            raise ValueError("No business model selected")
        profile = self.model.generator_profile
        rows = self._read_rows()
        arrivals: list[GroupArrival] = []
        if len(rows) > MAX_QUEUE_LENGTH:
            raise ValueError(f"Queue length cannot exceed {MAX_QUEUE_LENGTH}")
        for index, row in enumerate(rows):
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

            arrival_item = self.table.item(index, 0)
            group_id = ""
            if arrival_item is not None:
                group_id = str(arrival_item.data(Qt.ItemDataRole.UserRole) or "")
            arrivals.append(
                GroupArrival(
                    group_id=group_id or f"G{index + 1}",
                    arrival_time=row.arrival_time,
                    group_size=row.group_size,
                    dining_duration=row.dining_duration,
                    patience_override=row.patience_override,
                    is_reservation=row.is_reservation,
                    scheduled_time=row.scheduled_time,
                )
            )
        return sorted(arrivals, key=lambda row: (row.arrival_time, row.group_id))

    def _randomize(self) -> None:
        if not self.model:
            return
        count = cli_sample_arrival_count(self.model.name, random.Random())
        seed = random.randint(0, 1_000_000)
        scenario = cli_generate_scenario(
            business_model=self.model,
            seed=seed,
            arrival_count=count,
            duration=max(10, count * 3),
        )
        self.loaded_scenario = scenario
        self._populate_from_scenario(scenario.arrivals)

    def _add_row(
        self,
        arrival_time: int | None = None,
        group_size: int | None = None,
        dining_duration: int | None = None,
        patience_override: int | None = None,
        is_reservation: bool = False,
        scheduled_time: int | None = None,
        group_id: str | None = None,
    ) -> None:
        if self.table.rowCount() >= MAX_QUEUE_LENGTH:
            QMessageBox.warning(self, "Queue Limit", f"Queue length cannot exceed {MAX_QUEUE_LENGTH}")
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            "" if arrival_time is None else str(arrival_time),
            "" if group_size is None else str(group_size),
            "" if dining_duration is None else str(dining_duration),
            "" if patience_override is None else str(patience_override),
            "true" if is_reservation else "",
            "" if scheduled_time is None else str(scheduled_time),
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0 and group_id:
                item.setData(Qt.ItemDataRole.UserRole, group_id)
            self.table.setItem(row, column, item)

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _sort_by_arrival(self) -> None:
        if self._is_sorting:
            return
        self._is_sorting = True
        self.table.blockSignals(True)
        try:
            rows: list[list[str]] = []
            for row in range(self.table.rowCount()):
                values = [
                    self.table.item(row, column).text() if self.table.item(row, column) else ""
                    for column in range(self.table.columnCount())
                ]
                arrival_item = self.table.item(row, 0)
                group_id = ""
                if arrival_item is not None:
                    group_id = str(arrival_item.data(Qt.ItemDataRole.UserRole) or "")
                rows.append(values + [group_id])

            def arrival_key(values: list[str]) -> tuple[int, str, str]:
                try:
                    return int(values[0]), values[6], values[0]
                except ValueError:
                    return 10**9, values[6], values[0]

            rows.sort(key=arrival_key)
            self.table.setRowCount(0)
            for values in rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                group_id = values[6]
                for column, value in enumerate(values[:6]):
                    item = QTableWidgetItem(value)
                    if column == 0 and group_id:
                        item.setData(Qt.ItemDataRole.UserRole, group_id)
                    self.table.setItem(row, column, item)
        finally:
            self.table.blockSignals(False)
            self._is_sorting = False

    def _save_json(self) -> None:
        try:
            scenario = self._build_scenario()
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, "Cannot Save", str(error))
            return
        selected, _ = QFileDialog.getSaveFileName(self, "Save Scenario", "", "JSON Files (*.json)")
        if not selected:
            return
        write_scenario_json(Path(selected), scenario)
        QMessageBox.information(self, "Saved", f"Saved scenario to {selected}")

    def _run(self) -> None:
        try:
            scenario = self._build_scenario()
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid Queue", str(error))
            return
        result = cli_run_simulation(scenario)
        self.on_run(scenario, result)


class Layer3Widget(QWidget):
    def __init__(self, on_home) -> None:
        super().__init__()
        self.on_home = on_home
        self.scenario: Scenario | None = None
        self.result = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 32)
        layout.setSpacing(18)
        header = QLabel("Simulation Results")
        header.setProperty("title", True)
        header.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(header)
        layout.addSpacing(12)

        controls = QHBoxLayout()
        view_btn = QPushButton("View Scenario")
        view_btn.clicked.connect(self._toggle_sidebar)
        save_btn = QPushButton("Save Results Report (.txt)")
        save_btn.clicked.connect(self._save_report)
        home_btn = QPushButton("Return Home")
        home_btn.clicked.connect(self.on_home)
        controls.addWidget(view_btn)
        controls.addWidget(save_btn)
        controls.addWidget(home_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.stats_columns = QSplitter(Qt.Orientation.Horizontal)
        self.stats_left_text = QPlainTextEdit()
        self.stats_left_text.setReadOnly(True)
        self.stats_right_text = QPlainTextEdit()
        self.stats_right_text.setReadOnly(True)
        self.stats_columns.addWidget(self.stats_left_text)
        self.stats_columns.addWidget(self.stats_right_text)
        self.scenario_text = QPlainTextEdit()
        self.scenario_text.setReadOnly(True)
        self.scenario_text.hide()
        self.stats_left_text.setMinimumHeight(520)
        self.stats_right_text.setMinimumHeight(520)
        self.scenario_text.setMinimumHeight(520)
        self.splitter.addWidget(self.stats_columns)
        self.splitter.addWidget(self.scenario_text)
        layout.addWidget(self.splitter, 1)

    def set_result(self, scenario: Scenario, result) -> None:
        self.scenario = scenario
        self.result = result
        sections = _build_statistics_sections(result)
        self.stats_left_text.setPlainText(
            _format_statistics_column(
                sections,
                [
                    "Overview",
                    "Wait Times",
                    "Ordering And Seating",
                    "Reservations",
                ],
            )
        )
        self.stats_right_text.setPlainText(
            _format_statistics_column(
                sections,
                [
                    "Queue And Capacity",
                    "Queue Length By Queue",
                    "Total Wait Time By Group Size (arrival to seating)",
                    "Ordering Wait By Group Size",
                ],
            )
        )
        self.scenario_text.setPlainText(_format_scenario_text(scenario))

    def _toggle_sidebar(self) -> None:
        self.scenario_text.setVisible(not self.scenario_text.isVisible())

    def _save_report(self) -> None:
        if not self.result:
            return
        selected, _ = QFileDialog.getSaveFileName(self, "Save Report", "", "Text Files (*.txt)")
        if not selected:
            return
        cli_save_result(self.result, selected)
        QMessageBox.information(self, "Saved", f"Saved report to {selected}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Restaurant Queue Simulator")
        self.resize(1200, 850)

        self.state = AppState()
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.layer1 = Layer1Widget(self._on_model_selected, self._on_scenario_loaded)
        self.layer2 = Layer2Widget(self._on_run_clicked)
        self.layer3 = Layer3Widget(self._go_home)
        self.stack.addWidget(self.layer1)
        self.stack.addWidget(self.layer2)
        self.stack.addWidget(self.layer3)

    def _on_model_selected(self, model: BusinessModel) -> None:
        self.state = AppState(model=model, scenario=None, loaded_from_json=False)
        self.layer2.set_context(model=model, loaded_scenario=None)
        self.stack.setCurrentWidget(self.layer2)

    def _on_scenario_loaded(self, scenario: Scenario) -> None:
        builtin = get_builtin_models().get(scenario.business_model_name)
        min_group_size = min((a.group_size for a in scenario.arrivals), default=1)
        max_group_size = max((a.group_size for a in scenario.arrivals), default=1)
        if builtin is not None:
            profile = builtin.generator_profile
        else:
            profile = GeneratorProfile(
                min_group_size=min_group_size,
                max_group_size=max_group_size,
                group_size_weights={
                    group_size: 1.0
                    for group_size in range(min_group_size, max_group_size + 1)
                },
                min_dining_duration=min((a.dining_duration for a in scenario.arrivals), default=1),
                max_dining_duration=max((a.dining_duration for a in scenario.arrivals), default=1),
            )
        model = BusinessModel(
            name=scenario.business_model_name,
            queue_type=scenario.queue_type,
            strategy_name=scenario.strategy_name,
            tables=scenario.tables,
            generator_profile=profile,
            patience_threshold_mean=scenario.patience_threshold_mean,
            patience_threshold_sd=scenario.patience_threshold_sd,
            counters=scenario.counters,
            kiosks=scenario.kiosks,
            kiosk_usage_percent=scenario.kiosk_usage_percent,
            counter_order_time_min=scenario.counter_order_time_min,
            counter_order_time_max=scenario.counter_order_time_max,
            counter_order_time_mean=scenario.counter_order_time_mean,
            counter_order_time_sd=scenario.counter_order_time_sd,
            kiosk_order_time_min=scenario.kiosk_order_time_min,
            kiosk_order_time_max=scenario.kiosk_order_time_max,
            kiosk_order_time_mean=scenario.kiosk_order_time_mean,
            kiosk_order_time_sd=scenario.kiosk_order_time_sd,
            reservation_policy=scenario.reservation_policy,
            reserved_table_percent=scenario.reserved_table_percent,
            reservation_hold_before_min=scenario.reservation_hold_before_min,
            reservation_hold_after_min=scenario.reservation_hold_after_min,
            notes="Model reconstructed from JSON scenario",
        )
        self.state = AppState(model=model, scenario=scenario, loaded_from_json=True)
        self.layer2.set_context(model=model, loaded_scenario=scenario)
        self.stack.setCurrentWidget(self.layer2)

    def _on_run_clicked(self, scenario: Scenario, result) -> None:
        self.state.scenario = scenario
        self.layer3.set_result(scenario, result)
        self.stack.setCurrentWidget(self.layer3)

    def _go_home(self) -> None:
        self.state = AppState()
        self.stack.setCurrentWidget(self.layer1)


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            background-color: #f8f8f4;
            color: #242424;
            font-family: "Times New Roman", "Times", "Georgia", serif;
            font-size: 15px;
        }
        QLabel[title="true"] {
            font-size: 24px;
            font-weight: 600;
            padding: 4px 0 8px 0;
        }
        QLabel[cardTitle="true"] {
            font-size: 18px;
            font-weight: 600;
            padding: 0 0 2px 4px;
        }
        QGroupBox {
            background-color: #fcfcf9;
            border: 1px solid #d7d7d2;
            border-radius: 6px;
            margin-top: 0px;
            padding: 12px;
        }
        QPushButton {
            background-color: #f1f0eb;
            border: 1px solid #c9c8c2;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 15px;
        }
        QPushButton:hover {
            background-color: #e8e7e1;
        }
        QPlainTextEdit, QLineEdit, QComboBox, QTableWidget {
            background-color: #fffefb;
            border: 1px solid #d7d7d2;
            font-size: 15px;
        }
        QHeaderView::section {
            background-color: #efeee8;
            border: 1px solid #d7d7d2;
            padding: 6px;
            font-size: 15px;
        }
        """
    )
