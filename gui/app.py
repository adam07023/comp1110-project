from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
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
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.business_model import BusinessModel, GeneratorProfile
from domain.models import Scenario, TableInventory
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
    lines = [
        f"Model: {_friendly_model_name(model.name)}",
        f"Queue style: {model.queue_type.replace('_', ' ')}",
        f"Seating strategy: {model.strategy_name.replace('_', ' ')}",
        f"Group size range: {profile.min_group_size} to {profile.max_group_size} guests",
        f"Dining duration range: {profile.min_dining_duration} to {profile.max_dining_duration} minutes",
        f"Patience settings: mean {model.patience_threshold_mean:.0f} minutes, "
        f"standard deviation {model.patience_threshold_sd:.0f} minutes",
        f"Tables: {table_text}",
        f"Group-size weighting: {weight_text}",
        "",
        _model_summary(model),
    ]
    return "\n".join(lines)


def _format_stat_line(label: str, value: str) -> str:
    if label == "table_utilization_rate":
        return f"Table utilization: {float(value) * 100:.1f}%"

    if label == "simulation_end_time":
        return f"Simulation end time: {value} minutes"

    if label.startswith("average_wait_group_size_"):
        group_size = label.rsplit("_", 1)[-1]
        return f"Average wait for group size {group_size}: {value} minutes"

    label_map = {
        "served_groups": "Groups served",
        "rejected_groups": "Groups rejected",
        "total_groups": "Total groups",
        "average_wait_time": "Average wait time",
        "min_wait_time": "Minimum wait time",
        "max_wait_time": "Maximum wait time",
        "longest_queue_length": "Maximum queue length",
        "shortest_queue_length": "Minimum queue length",
    }
    friendly = label_map.get(label, label.replace("_", " ").capitalize())
    if "wait" in label:
        return f"{friendly}: {value} minutes"
    return f"{friendly}: {value}"


def _format_statistics_text(result) -> str:
    lines: list[str] = []
    for raw_line in result.statistics.to_pretty_text().splitlines():
        if "=" not in raw_line:
            lines.append(raw_line)
            continue
        label, value = raw_line.split("=", 1)
        lines.append(_format_stat_line(label, value))
    return "\n".join(lines)


def _format_scenario_text(scenario: Scenario) -> str:
    lines = [
        f"Model: {_friendly_model_name(scenario.business_model_name)}",
        f"Queue style: {scenario.queue_type.replace('_', ' ')}",
        f"Seating strategy: {scenario.strategy_name.replace('_', ' ')}",
        "Tables: " + ", ".join(f"{table.count} x {table.seats}-seat" for table in scenario.tables),
        "",
        "Arrivals:",
    ]
    for row in scenario.arrivals:
        patience_text = (
            f"{row.patience_override} minutes" if row.patience_override is not None else "automatic"
        )
        lines.append(
            f"- At {row.arrival_time} minutes: group of {row.group_size}, "
            f"dining for {row.dining_duration} minutes, patience {patience_text}"
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

        self.name_input = QLineEdit()
        self.min_group_input = QSpinBox()
        self.max_group_input = QSpinBox()
        self.min_dining_input = QSpinBox()
        self.max_dining_input = QSpinBox()
        self.patience_mean_input = QLineEdit("20")
        self.patience_sd_input = QLineEdit("6")
        self.queue_type_input = QLineEdit("single_queue")
        self.strategy_input = QLineEdit("fifo_fit")
        self.tables_input = QLineEdit("2:4,4:4")
        self.weights_input = QLineEdit("1:0.3,2:0.3,3:0.2,4:0.2")

        for spin in (self.min_group_input, self.max_group_input):
            spin.setRange(1, 20)
        for spin in (self.min_dining_input, self.max_dining_input):
            spin.setRange(1, 500)

        self.min_group_input.setValue(1)
        self.max_group_input.setValue(4)
        self.min_dining_input.setValue(10)
        self.max_dining_input.setValue(60)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Model Name", self.name_input)
        form.addRow("Min Group Size", self.min_group_input)
        form.addRow("Max Group Size", self.max_group_input)
        form.addRow("Group Weights (size:weight,...)", self.weights_input)
        form.addRow("Min Dining Duration", self.min_dining_input)
        form.addRow("Max Dining Duration", self.max_dining_input)
        form.addRow("Patience Mean", self.patience_mean_input)
        form.addRow("Patience SD", self.patience_sd_input)
        form.addRow("Queue Type", self.queue_type_input)
        form.addRow("Strategy", self.strategy_input)
        form.addRow("Tables (seats:count,...)", self.tables_input)
        layout.addLayout(form)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancel")
        save = QPushButton("Select")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def build_model(self) -> BusinessModel:
        name = self.name_input.text().strip()
        if not name:
            raise ValueError("Model name is required")

        min_group = self.min_group_input.value()
        max_group = self.max_group_input.value()
        if min_group > max_group:
            raise ValueError("Min group size cannot exceed max group size")

        min_dining = self.min_dining_input.value()
        max_dining = self.max_dining_input.value()
        if min_dining > max_dining:
            raise ValueError("Min dining duration cannot exceed max dining duration")

        weights = _parse_weights(self.weights_input.text(), min_group, max_group)
        tables = _parse_tables(self.tables_input.text())
        patience_mean = float(self.patience_mean_input.text())
        patience_sd = float(self.patience_sd_input.text())
        if patience_mean <= 0 or patience_sd < 0:
            raise ValueError("Patience mean must be positive and SD cannot be negative")

        return BusinessModel(
            name=name,
            queue_type=self.queue_type_input.text().strip() or "single_queue",
            strategy_name=self.strategy_input.text().strip() or "fifo_fit",
            tables=tables,
            generator_profile=GeneratorProfile(
                min_group_size=min_group,
                max_group_size=max_group,
                group_size_weights=weights,
                min_dining_duration=min_dining,
                max_dining_duration=max_dining,
            ),
            patience_threshold_mean=patience_mean,
            patience_threshold_sd=patience_sd,
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
        QMessageBox.information(self, "Model Parameters", _format_model_details(model))

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
        try:
            scenario = load_scenario_json(Path(selected))
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Failed to Load", str(error))
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

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [
                "Arrival Time (min)",
                "Group Size",
                "Dining Duration (min)",
                "Patience (min)",
            ]
        )
        self.table.setColumnWidth(0, 200)  # Arrival Time
        self.table.setColumnWidth(1, 200)  # Group Size
        self.table.setColumnWidth(2, 200)  # Dining Duration
        self.table.setColumnWidth(3, 200)  # Patience
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

            if not arrival_item or not group_item or not dining_item:
                raise ValueError("Arrival, group size, and dining duration are required")

            patience_text = patience_item.text().strip() if patience_item else ""
            rows.append(
                QueueRowInput(
                    arrival_time=int(arrival_item.text()),
                    group_size=int(group_item.text()),
                    dining_duration=int(dining_item.text()),
                    patience_override=int(patience_text) if patience_text else None,
                )
            )
        return rows

    def _build_scenario(self) -> Scenario:
        if not self.model:
            raise ValueError("No business model selected")

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
        )

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
        ]
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(value))

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _sort_by_arrival(self) -> None:
        if self._is_sorting:
            return
        self._is_sorting = True
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
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
        self.stats_text = QPlainTextEdit()
        self.stats_text.setReadOnly(True)
        self.scenario_text = QPlainTextEdit()
        self.scenario_text.setReadOnly(True)
        self.scenario_text.hide()
        self.splitter.addWidget(self.stats_text)
        self.splitter.addWidget(self.scenario_text)
        layout.addWidget(self.splitter)
        layout.addStretch(1)

    def set_result(self, scenario: Scenario, result) -> None:
        self.scenario = scenario
        self.result = result
        self.stats_text.setPlainText(_format_statistics_text(result))
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
        self.resize(1100, 700)

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
        model = builtin
        if model is None:
            model = BusinessModel(
                name=scenario.business_model_name,
                queue_type=scenario.queue_type,
                strategy_name=scenario.strategy_name,
                tables=scenario.tables,
                generator_profile=GeneratorProfile(
                    min_group_size=min((a.group_size for a in scenario.arrivals), default=1),
                    max_group_size=max((a.group_size for a in scenario.arrivals), default=1),
                    group_size_weights={1: 1.0},
                    min_dining_duration=min((a.dining_duration for a in scenario.arrivals), default=1),
                    max_dining_duration=max((a.dining_duration for a in scenario.arrivals), default=1),
                ),
                patience_threshold_mean=scenario.patience_threshold_mean,
                patience_threshold_sd=scenario.patience_threshold_sd,
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
        QPlainTextEdit, QLineEdit, QSpinBox, QTableWidget {
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
