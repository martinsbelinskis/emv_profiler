"""PyQt6 GUI for mc_profile_parser."""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from mc_profile_parser.parser import (
    ComparisonRow,
    DataElementRow,
    compare_profiles,
    export_comparison_csv,
    export_csv,
    parse_profile,
)

PROFILE_COLS = [f.name for f in fields(DataElementRow)]
CMP_COLS = [f.name for f in fields(ComparisonRow)]
CMP_STATUS_COL = CMP_COLS.index("status")

STATUS_COLORS: dict[str, QColor] = {
    "identical": QColor("#C8E6C9"),
    "different":  QColor("#FFF9C4"),
    "only_in_1":  QColor("#FFCDD2"),
    "only_in_2":  QColor("#BBDEFB"),
}

STATUS_FILTER_OPTIONS: list[tuple[str, str | None]] = [
    ("All statuses", None),
    ("Different only", "different"),
    ("Only in Profile 1", "only_in_1"),
    ("Only in Profile 2", "only_in_2"),
    ("Identical only", "identical"),
]

TAB_P1  = 0
TAB_P2  = 1
TAB_CMP = 2


class _StatusFilterProxy(QSortFilterProxyModel):
    """Proxy that combines a free-text filter with an optional status filter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status: str | None = None
        self._text: str = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_status(self, status: str | None) -> None:
        self._status = status
        self.invalidateFilter()

    def set_text(self, text: str) -> None:
        self._text = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if self._status is not None:
            status_item = model.item(source_row, CMP_STATUS_COL)
            if not status_item or status_item.text() != self._status:
                return False
        if self._text:
            for col in range(model.columnCount()):
                item = model.item(source_row, col)
                if item and self._text in item.text().lower():
                    return True
            return False
        return True


def _make_table() -> QTableView:
    t = QTableView()
    t.setSortingEnabled(True)
    t.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(False)
    return t


def _make_model(columns: list[str]) -> QStandardItemModel:
    m = QStandardItemModel(0, len(columns))
    m.setHorizontalHeaderLabels(columns)
    return m


def _simple_proxy(model: QStandardItemModel) -> QSortFilterProxyModel:
    p = QSortFilterProxyModel()
    p.setSourceModel(model)
    p.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    p.setFilterKeyColumn(-1)
    return p


def _legend_widget() -> QWidget:
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    layout.addWidget(QLabel("Legend:"))
    for status, color in STATUS_COLORS.items():
        swatch = QLabel("  ")
        swatch.setStyleSheet(f"background:{color.name()}; border:1px solid #aaa;")
        label = QLabel(status.replace("_", " ").title())
        layout.addWidget(swatch)
        layout.addWidget(label)
    layout.addStretch()
    return w


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MC Profile Parser — Comparison Tool")
        self.resize(1200, 700)

        self._rows_1: list[DataElementRow] = []
        self._rows_2: list[DataElementRow] = []
        self._cmp_rows: list[ComparisonRow] = []

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setSpacing(8)
        vbox.setContentsMargins(10, 10, 10, 10)

        # Profile picker grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)

        self._path_edit: list[QLineEdit] = []
        self._parse_btn: list[QPushButton] = []

        for i in range(2):
            n = i + 1
            label = QLabel(f"Profile {n}:")
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select .profile file for Profile {n}…")
            edit.setReadOnly(True)
            browse = QPushButton("Browse…")
            browse.setFixedWidth(85)
            browse.clicked.connect(lambda _, idx=i: self._browse(idx))
            parse_btn = QPushButton(f"Parse {n}")
            parse_btn.setFixedWidth(75)
            parse_btn.setEnabled(False)
            parse_btn.clicked.connect(lambda _, idx=i: self._parse(idx))
            grid.addWidget(label,     i, 0)
            grid.addWidget(edit,      i, 1)
            grid.addWidget(browse,    i, 2)
            grid.addWidget(parse_btn, i, 3)
            self._path_edit.append(edit)
            self._parse_btn.append(parse_btn)

        self._compare_btn = QPushButton("⚡ Compare")
        self._compare_btn.setFixedWidth(110)
        self._compare_btn.setEnabled(False)
        self._compare_btn.clicked.connect(self._compare)
        grid.addWidget(self._compare_btn, 0, 4, 2, 1, Qt.AlignmentFlag.AlignVCenter)

        vbox.addLayout(grid)

        # Tabs
        self._tabs = QTabWidget()
        # Signal connected at end of _build_ui, after all widgets exist

        # --- Profile 1 tab ---
        self._model_1 = _make_model(PROFILE_COLS)
        self._proxy_1 = _simple_proxy(self._model_1)
        self._table_1 = _make_table()
        self._table_1.setModel(self._proxy_1)
        self._tabs.addTab(self._table_1, "Profile 1")

        # --- Profile 2 tab ---
        self._model_2 = _make_model(PROFILE_COLS)
        self._proxy_2 = _simple_proxy(self._model_2)
        self._table_2 = _make_table()
        self._table_2.setModel(self._proxy_2)
        self._tabs.addTab(self._table_2, "Profile 2")

        # --- Comparison tab ---
        self._model_cmp = _make_model(CMP_COLS)
        self._proxy_cmp = _StatusFilterProxy()
        self._proxy_cmp.setSourceModel(self._model_cmp)
        self._table_cmp = _make_table()
        self._table_cmp.setModel(self._proxy_cmp)
        self._tabs.addTab(self._table_cmp, "⚡ Comparison")

        vbox.addWidget(self._tabs)

        # Bottom bar
        bottom = QHBoxLayout()

        bottom.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search across all columns…")
        self._filter_edit.textChanged.connect(self._on_filter_text)
        bottom.addWidget(self._filter_edit)

        self._status_combo = QComboBox()
        self._status_combo.setFixedWidth(175)
        for label, _ in STATUS_FILTER_OPTIONS:
            self._status_combo.addItem(label)
        self._status_combo.currentIndexChanged.connect(self._on_status_filter)
        self._status_combo.setVisible(False)
        bottom.addWidget(self._status_combo)

        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setFixedWidth(120)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export)
        bottom.addWidget(self._export_btn)

        vbox.addLayout(bottom)
        vbox.addWidget(_legend_widget())

        # Connect tab signal now that all child widgets exist
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self.statusBar().showMessage("Ready — select two profiles and click Compare.")

    # ── slots ─────────────────────────────────────────────────────────────

    def _browse(self, idx: int) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select Profile {idx + 1}",
            str(Path.home()),
            "Profile files (*.profile);;All files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._path_edit[idx].setText(path)
            self._parse_btn[idx].setEnabled(True)
            # Stale guard: clear comparison if either path changes
            self._clear_comparison()

    def _parse(self, idx: int) -> None:
        path = self._path_edit[idx].text().strip()
        if not path:
            return
        try:
            # include_empty=True so comparison sees all elements
            rows = parse_profile(path, include_empty=True)
        except Exception as exc:
            QMessageBox.critical(self, "Parse error", str(exc))
            return

        model = [self._model_1, self._model_2][idx]
        rows_attr = ["_rows_1", "_rows_2"][idx]
        setattr(self, rows_attr, rows)
        self._fill_profile_model(model, rows)
        self._tabs.setCurrentIndex(idx)
        self._clear_comparison()
        self._export_btn.setEnabled(True)

        n_with_value = sum(1 for r in rows if r.value)
        self.statusBar().showMessage(
            f"Profile {idx + 1}: {len(rows)} elements parsed "
            f"({n_with_value} with non-empty value) — {Path(path).name}"
        )
        self._compare_btn.setEnabled(bool(self._rows_1 and self._rows_2))

    def _compare(self) -> None:
        if not self._rows_1 or not self._rows_2:
            return
        self._cmp_rows = compare_profiles(self._rows_1, self._rows_2)
        self._fill_comparison_model(self._cmp_rows)
        self._tabs.setCurrentIndex(TAB_CMP)
        self._export_btn.setEnabled(True)

        counts = {s: 0 for s in STATUS_COLORS}
        for r in self._cmp_rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        self.statusBar().showMessage(
            f"Comparison: {counts['different']} different · "
            f"{counts['only_in_1']} only in P1 · "
            f"{counts['only_in_2']} only in P2 · "
            f"{counts['identical']} identical"
        )

    def _export(self) -> None:
        tab = self._tabs.currentIndex()
        if tab == TAB_CMP:
            self._export_comparison()
        else:
            self._export_profile(tab)

    def _export_profile(self, tab: int) -> None:
        rows = self._rows_1 if tab == TAB_P1 else self._rows_2
        # Export only non-empty value rows (matching single-profile semantics)
        rows = [r for r in rows if r.value]
        n = tab + 1
        dest = self._save_dialog(f"profile_{n}_export.csv")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8") as f:
            export_csv(rows, f)
        self.statusBar().showMessage(f"Exported {len(rows)} rows → {dest}")

    def _export_comparison(self) -> None:
        # Export whatever is visible through current filter
        proxy = self._proxy_cmp
        visible: list[ComparisonRow] = []
        for proxy_row in range(proxy.rowCount()):
            src_row = proxy.mapToSource(proxy.index(proxy_row, 0)).row()
            visible.append(self._cmp_rows[src_row])

        dest = self._save_dialog("comparison_export.csv")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8") as f:
            export_comparison_csv(visible, f)
        self.statusBar().showMessage(f"Exported {len(visible)} comparison rows → {dest}")

    def _on_filter_text(self, text: str) -> None:
        tab = self._tabs.currentIndex()
        if tab == TAB_P1:
            self._proxy_1.setFilterFixedString(text)
        elif tab == TAB_P2:
            self._proxy_2.setFilterFixedString(text)
        else:
            self._proxy_cmp.set_text(text)

    def _on_status_filter(self, index: int) -> None:
        _, status = STATUS_FILTER_OPTIONS[index]
        self._proxy_cmp.set_status(status)

    def _on_tab_changed(self, index: int) -> None:
        self._filter_edit.clear()
        is_cmp = index == TAB_CMP
        self._status_combo.setVisible(is_cmp)
        if is_cmp:
            self._status_combo.setCurrentIndex(0)
        has_data = (
            (index == TAB_P1 and bool(self._rows_1))
            or (index == TAB_P2 and bool(self._rows_2))
            or (index == TAB_CMP and bool(self._cmp_rows))
        )
        self._export_btn.setEnabled(has_data)

    # ── helpers ───────────────────────────────────────────────────────────

    def _fill_profile_model(self, model: QStandardItemModel, rows: list[DataElementRow]) -> None:
        model.setRowCount(0)
        for row in rows:
            items = [QStandardItem(str(getattr(row, col))) for col in PROFILE_COLS]
            model.appendRow(items)

    def _fill_comparison_model(self, rows: list[ComparisonRow]) -> None:
        self._model_cmp.setRowCount(0)
        for row in rows:
            color = STATUS_COLORS.get(row.status, QColor("white"))
            items: list[QStandardItem] = []
            for col in CMP_COLS:
                item = QStandardItem(str(getattr(row, col)))
                item.setBackground(color)
                items.append(item)
            self._model_cmp.appendRow(items)

    def _clear_comparison(self) -> None:
        self._cmp_rows = []
        self._model_cmp.setRowCount(0)
        if self._tabs.currentIndex() == TAB_CMP:
            self._export_btn.setEnabled(False)

    def _save_dialog(self, default_name: str) -> str:
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export CSV",
            str(Path.home() / default_name),
            "CSV files (*.csv);;All files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        return dest


def run_gui() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

