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
from fileio.result_writer import write_result_file
from generation.randomizer import generate_random_scenario
from presets.builtins import get_builtin_models
from simulation.engine import run_simulation

from gui.queue_logic import QueueRowInput, sample_arrival_count, validate_queue_rows
from gui.queue_logic import MAX_QUEUE_LENGTH


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
        title = QLabel("Choose Restaurant Configuration")
        title.setProperty("title", True)
        layout.addWidget(title)

        grid = QGridLayout()
        ordered = ["fast_food", "fine_dining", "casual_dining", "cafe", "food_truck"]
        for idx, key in enumerate(ordered):
            model = self.models[key]
            card = QGroupBox(model.name.replace("_", " ").title())
            card_layout = QVBoxLayout(card)
            info = QLabel(model.notes)
            info.setWordWrap(True)
            card_layout.addWidget(info)
            view_btn = QPushButton("View Parameters")
            select_btn = QPushButton("Select Model")
            view_btn.clicked.connect(lambda _checked=False, selected=model: self._view_model(selected))
            select_btn.clicked.connect(lambda _checked=False, selected=model: self.on_model_selected(selected))
            card_layout.addWidget(view_btn)
            card_layout.addWidget(select_btn)
            grid.addWidget(card, idx // 3, idx % 3)

        custom_card = QGroupBox("Customize Restaurant")
        custom_layout = QVBoxLayout(custom_card)
        custom_layout.addWidget(QLabel("Build your own parameter set."))
        custom_btn = QPushButton("Select")
        custom_btn.clicked.connect(self._customize)
        custom_layout.addWidget(custom_btn)
        grid.addWidget(custom_card, 1, 2)
        layout.addLayout(grid)

        load_row = QHBoxLayout()
        load_btn = QPushButton("Load Scenario JSON")
        load_btn.clicked.connect(self._load_json)
        load_row.addWidget(load_btn)
        load_row.addStretch(1)
        layout.addLayout(load_row)

    def _view_model(self, model: BusinessModel) -> None:
        profile = model.generator_profile
        details = (
            f"Name: {model.name}\nQueue Type: {model.queue_type}\nStrategy: {model.strategy_name}\n"
            f"Group Size: {profile.min_group_size}-{profile.max_group_size}\n"
            f"Dining Duration: {profile.min_dining_duration}-{profile.max_dining_duration}\n"
            f"Weights: {profile.group_size_weights}\n"
            f"Patience: mean={model.patience_threshold_mean}, sd={model.patience_threshold_sd}\n"
            f"Tables: {[f'{t.seats}x{t.count}' for t in model.tables]}"
        )
        QMessageBox.information(self, "Model Parameters", details)

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
        header = QLabel("Build Queue")
        header.setProperty("title", True)
        layout.addWidget(header)

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
        self.table.setHorizontalHeaderLabels(["Arrival Time", "Group Size", "Dining Duration", "Patience"])
        self.table.itemChanged.connect(self._sort_by_arrival)
        layout.addWidget(self.table)

        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

    def set_context(self, model: BusinessModel, loaded_scenario: Scenario | None = None) -> None:
        self.model = model
        self.loaded_scenario = loaded_scenario
        self._populate_from_scenario(loaded_scenario.arrivals if loaded_scenario else [])

    def _populate_from_scenario(self, arrivals) -> None:
        self.table.setRowCount(0)
        for arrival in arrivals:
            self._add_row(
                arrival.arrival_time,
                arrival.group_size,
                arrival.dining_duration,
                arrival.patience_override,
            )

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

        arrivals = validate_queue_rows(self._read_rows(), self.model)
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
        count = sample_arrival_count(self.model.name, random.Random())
        seed = random.randint(0, 1_000_000)
        scenario = generate_random_scenario(
            business_model=self.model,
            seed=seed,
            arrival_count=count,
            duration=max(10, count * 3),
            generated=True,
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
        result = run_simulation(scenario)
        self.on_run(scenario, result)


class Layer3Widget(QWidget):
    def __init__(self, on_home) -> None:
        super().__init__()
        self.on_home = on_home
        self.scenario: Scenario | None = None
        self.result = None

        layout = QVBoxLayout(self)
        header = QLabel("Simulation Results")
        header.setProperty("title", True)
        layout.addWidget(header)

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

    def set_result(self, scenario: Scenario, result) -> None:
        self.scenario = scenario
        self.result = result
        self.stats_text.setPlainText(result.statistics.to_pretty_text())
        lines = [
            f"model={scenario.business_model_name}",
            f"queue_type={scenario.queue_type}",
            f"strategy={scenario.strategy_name}",
            "tables=" + ", ".join(f"{table.seats}:{table.count}" for table in scenario.tables),
            "arrivals:",
        ]
        for row in scenario.arrivals:
            lines.append(
                f"- t={row.arrival_time}, size={row.group_size}, "
                f"duration={row.dining_duration}, patience={row.patience_override}"
            )
        self.scenario_text.setPlainText("\n".join(lines))

    def _toggle_sidebar(self) -> None:
        self.scenario_text.setVisible(not self.scenario_text.isVisible())

    def _save_report(self) -> None:
        if not self.result:
            return
        selected, _ = QFileDialog.getSaveFileName(self, "Save Report", "", "Text Files (*.txt)")
        if not selected:
            return
        write_result_file(Path(selected), self.result)
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
            background-color: #f1f1ee;
            color: #242424;
            font-size: 13px;
        }
        QLabel[title="true"] {
            font-size: 24px;
            font-weight: 600;
            padding: 4px 0 8px 0;
        }
        QGroupBox {
            border: 1px solid #d0d0cc;
            border-radius: 6px;
            margin-top: 8px;
            padding: 10px;
        }
        QPushButton {
            background-color: #ebebe6;
            border: 1px solid #c7c7c2;
            border-radius: 4px;
            padding: 6px 10px;
        }
        QPushButton:hover {
            background-color: #e1e1dc;
        }
        """
    )
