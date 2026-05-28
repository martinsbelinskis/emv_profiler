"""PyQt6 GUI for mc_profile_parser."""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import fields
from pathlib import Path

from PyQt6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import json

from mc_profile_parser.env_template import ENV_TEMPLATE, EnvEntry
from mc_profile_parser.visa_env_template import VISA_ENV_TEMPLATE, VisaEnvEntry
from mc_profile_parser.parser import (
    ComparisonRow,
    DataElementRow,
    EnvCompareRow,
    VisaElementRow,
    VisaComparisonRow,
    compare_profiles,
    compare_visa_profiles,
    compare_env_files,
    export_comparison_csv,
    export_csv,
    export_env,
    export_env_comparison_csv,
    export_visa_csv,
    export_visa_comparison_csv,
    export_visa_env,
    parse_env_file,
    parse_profile,
    parse_visa_profile,
    _visa_elem_id,
)

PROFILE_COLS = [f.name for f in fields(DataElementRow)]
CMP_COLS = [f.name for f in fields(ComparisonRow)]
CMP_STATUS_COL = CMP_COLS.index("status")

VISA_COLS = [f.name for f in fields(VisaElementRow)]
VISA_CMP_COLS = [f.name for f in fields(VisaComparisonRow)]
VISA_CMP_STATUS_COL = VISA_CMP_COLS.index("status")

STATUS_COLORS: dict[str, QColor] = {
    "identical": QColor("#C8E6C9"),
    "different":  QColor("#FFF9C4"),
    "only_in_1":  QColor("#FFCDD2"),
    "only_in_2":  QColor("#BBDEFB"),
}

# (button label, status value or None for "All", hex color)
FILTER_BUTTONS: list[tuple[str, str | None, str]] = [
    ("All",         None,        "#E0E0E0"),
    ("Identical",   "identical", STATUS_COLORS["identical"].name()),
    ("Different",   "different", STATUS_COLORS["different"].name()),
    ("Only in P1",  "only_in_1", STATUS_COLORS["only_in_1"].name()),
    ("Only in P2",  "only_in_2", STATUS_COLORS["only_in_2"].name()),
]

TAB_P1  = 0
TAB_P2  = 1
TAB_CMP = 2
TAB_ENV = 3
TAB_ENVCMP = 4

_NOT_MAPPED = "(not mapped)"


class _StatusFilterProxy(QSortFilterProxyModel):
    """Proxy combining a free-text filter with an optional status-column filter.

    ``status_col`` is the column index that holds the status string.
    """

    def __init__(self, status_col: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_col = status_col
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
            status_item = model.item(source_row, self._status_col)
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


@contextlib.contextmanager
def _suppress_glib_stderr():
    """Suppress GLib/GIO critical warnings printed to stderr by the native file dialog."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)


def _make_color_filter_bar() -> tuple[QWidget, QButtonGroup]:
    """Return a bar of checkable colored buttons + the QButtonGroup that owns them.

    The buttons act as exclusive status filters for the Comparison tab and
    simultaneously serve as a color legend.
    """
    bar = QWidget()
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(QLabel("Filter / Legend:"))

    group = QButtonGroup(bar)
    group.setExclusive(True)

    for idx, (label, _status, color) in enumerate(FILTER_BUTTONS):
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(idx == 0)  # "All" checked by default
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {color}; border: 2px solid transparent;"
            f"  border-radius: 4px; padding: 3px 10px;"
            f"}}"
            f"QPushButton:checked {{"
            f"  border: 2px solid #444; font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ border: 2px solid #888; }}"
        )
        group.addButton(btn, idx)
        layout.addWidget(btn)

    layout.addStretch()
    return bar, group


# ── ENV Export Tab ────────────────────────────────────────────────────────────

class EnvExportTab(QWidget):
    """Tab for mapping profile data elements to ENV variable names and exporting a .env file."""

    _ENV_COLS = ["ENV Variable", "Tag", "Type", "Profile Element", "Override Value", "Preview"]
    _COL_VAR, _COL_TAG, _COL_TYPE, _COL_ELEM, _COL_OVR, _COL_PREV = range(6)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # _source_rows[0] = Profile 1 rows, _source_rows[1] = Profile 2 rows
        self._source_rows: list[list[DataElementRow]] = [[], []]
        # Ordered list of (element_id, display_label) for the current source profile
        self._elem_options: list[tuple[str, str]] = []
        # id -> DataElementRow for quick lookup
        self._id_to_row: dict[str, DataElementRow] = {}
        self._combos: list[QComboBox] = []
        self._build_ui()

    # ── construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top bar
        top = QHBoxLayout()
        top.addWidget(QLabel("Source profile:"))
        self._src_combo = QComboBox()
        self._src_combo.addItems(["Profile 1", "Profile 2"])
        self._src_combo.setFixedWidth(110)
        self._src_combo.currentIndexChanged.connect(self._on_source_changed)
        top.addWidget(self._src_combo)
        top.addStretch()
        load_btn = QPushButton("Load Mapping…")
        load_btn.clicked.connect(self._load_mapping)
        save_btn = QPushButton("Save Mapping…")
        save_btn.clicked.connect(self._save_mapping)
        top.addWidget(load_btn)
        top.addWidget(save_btn)
        layout.addLayout(top)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search variable names, tags, values…")
        self._filter_edit.textChanged.connect(self._apply_filter)
        clr_btn = QPushButton("✕")
        clr_btn.setFixedWidth(28)
        clr_btn.setToolTip("Clear filter")
        clr_btn.clicked.connect(self._filter_edit.clear)
        filter_row.addWidget(self._filter_edit)
        filter_row.addWidget(clr_btn)
        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget(len(ENV_TEMPLATE), len(self._ENV_COLS))
        self._table.setHorizontalHeaderLabels(self._ENV_COLS)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self._COL_VAR,  QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self._COL_TAG,  QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_ELEM, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(self._COL_OVR,  QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(self._COL_PREV, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(self._COL_ELEM, 320)
        self._table.setColumnWidth(self._COL_OVR,  160)
        self._table.verticalHeader().setVisible(False)
        # Only override column is editable — all others are read-only
        self._table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked |
                                    QTableWidget.EditTrigger.AnyKeyPressed)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)

        for row_idx, entry in enumerate(ENV_TEMPLATE):
            def _ro(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return item

            self._table.setItem(row_idx, self._COL_VAR,  _ro(entry.var_name))
            self._table.setItem(row_idx, self._COL_TAG,  _ro(entry.primary_tag, Qt.AlignmentFlag.AlignCenter))
            self._table.setItem(row_idx, self._COL_TYPE, _ro(entry.type_hint or "hex", Qt.AlignmentFlag.AlignCenter))

            combo = QComboBox()
            combo.addItem(_NOT_MAPPED)
            combo.currentIndexChanged.connect(lambda _, r=row_idx: self._update_preview(r))
            self._combos.append(combo)
            self._table.setCellWidget(row_idx, self._COL_ELEM, combo)

            # Override Value column — editable; pre-fill from entry.default_value
            ovr_item = QTableWidgetItem(entry.default_value)
            ovr_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row_idx, self._COL_OVR, ovr_item)

            self._table.setItem(row_idx, self._COL_PREV, _ro("—"))

        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.addStretch()
        self._export_btn = QPushButton("Export .env…")
        self._export_btn.clicked.connect(self._export_env)
        bottom.addWidget(self._export_btn)
        layout.addLayout(bottom)

    # ── public API ────────────────────────────────────────────────────────

    def update_profile(self, idx: int, rows: list[DataElementRow]) -> None:
        """Called by MainWindow when a profile is parsed."""
        self._source_rows[idx] = rows
        if self._src_combo.currentIndex() == idx:
            self._on_source_changed(idx)

    # ── slots ─────────────────────────────────────────────────────────────

    def _on_source_changed(self, idx: int) -> None:
        rows = self._source_rows[idx]
        self._id_to_row = {r.id: r for r in rows}
        # Build ordered option list; disambiguate duplicate tags with interface/section context
        self._elem_options = []
        for r in rows:
            label = f"{r.tag} — {r.name}  [{r.interface}/{r.section}]"
            self._elem_options.append((r.id, label))
        self._refresh_combos(keep_selection=False)

    def _refresh_combos(self, *, keep_selection: bool) -> None:
        labels = [_NOT_MAPPED] + [label for _, label in self._elem_options]
        ids    = [""]          + [eid   for eid,  _   in self._elem_options]

        self._table.blockSignals(True)
        for row_idx, (combo, entry) in enumerate(zip(self._combos, ENV_TEMPLATE)):
            prev_id = combo.currentData() or ""
            combo.blockSignals(True)
            combo.clear()
            for label, eid in zip(labels, ids):
                combo.addItem(label, userData=eid)

            matched = False
            if keep_selection and prev_id:
                # Try to restore previous element-id selection
                for i, eid in enumerate(ids):
                    if eid == prev_id:
                        combo.setCurrentIndex(i)
                        matched = True
                        break

            if not matched:
                # Auto-map: find first profile element whose tag matches any of entry.tags
                for tag in entry.tags:
                    for i, (eid, _) in enumerate(self._elem_options, start=1):
                        row = self._id_to_row.get(eid)
                        if row and row.tag.upper() == tag.upper():
                            combo.setCurrentIndex(i)
                            matched = True
                            break
                    if matched:
                        break

            combo.blockSignals(False)

            # When switching source profile (not keeping selection), reset override to default
            if not keep_selection:
                ovr_item = self._table.item(row_idx, self._COL_OVR)
                if ovr_item is not None:
                    ovr_item.setText(entry.default_value)

        self._table.blockSignals(False)
        for row_idx in range(len(ENV_TEMPLATE)):
            self._update_preview(row_idx)

    def _apply_filter(self, text: str) -> None:
        """Show/hide rows whose variable name, tag, or preview match *text*."""
        low = text.lower()
        for row_idx in range(self._table.rowCount()):
            if not low:
                self._table.setRowHidden(row_idx, False)
                continue
            def _cell(col: int) -> str:
                item = self._table.item(row_idx, col)
                return item.text().lower() if item else ""
            combo = self._combos[row_idx] if row_idx < len(self._combos) else None
            combo_text = combo.currentText().lower() if combo else ""
            visible = (
                low in _cell(self._COL_VAR)
                or low in _cell(self._COL_TAG)
                or low in _cell(self._COL_TYPE)
                or low in _cell(self._COL_PREV)
                or low in _cell(self._COL_OVR)
                or low in combo_text
            )
            self._table.setRowHidden(row_idx, not visible)

    def _update_preview(self, row_idx: int) -> None:
        from mc_profile_parser.parser import _hex_to_display
        combo = self._combos[row_idx]
        elem_id: str = combo.currentData() or ""
        entry = ENV_TEMPLATE[row_idx]

        # Override takes priority over profile mapping
        ovr_item = self._table.item(row_idx, self._COL_OVR)
        override = (ovr_item.text().strip() if ovr_item else "")

        if override:
            preview = override
        else:
            row = self._id_to_row.get(elem_id)
            hex_val = row.value if row else ""
            preview = _hex_to_display(hex_val, entry.type_hint) if hex_val else "—"

        prev_item = self._table.item(row_idx, self._COL_PREV)
        if prev_item:
            # Block signals to avoid recursive itemChanged
            self._table.blockSignals(True)
            prev_item.setText(preview)
            self._table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Refresh preview when the override column is edited."""
        if item.column() == self._COL_OVR:
            self._update_preview(item.row())

    def _get_mapping(self) -> dict[str, dict]:
        """Return {var_name: {element_id, override}} for all rows."""
        result: dict[str, dict] = {}
        for i, (combo, entry) in enumerate(zip(self._combos, ENV_TEMPLATE)):
            elem_id = combo.currentData() or ""
            ovr_item = self._table.item(i, self._COL_OVR)
            override = (ovr_item.text().strip() if ovr_item else "")
            result[entry.var_name] = {"element_id": elem_id, "override": override}
        return result

    def _load_mapping(self) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getOpenFileName(
                self, "Load Mapping", str(Path.home()),
                "JSON files (*.json);;All files (*)",
            )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw: dict = json.load(f)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return

        ids = [""] + [eid for eid, _ in self._elem_options]
        self._table.blockSignals(True)
        for i, entry in enumerate(ENV_TEMPLATE):
            val = raw.get(entry.var_name)
            if val is None:
                continue
            # Support old format (plain string element_id) and new format (dict)
            if isinstance(val, str):
                elem_id, override = val, ""
            else:
                elem_id = val.get("element_id", "")
                override = val.get("override", "")

            if elem_id in ids:
                self._combos[i].blockSignals(True)
                self._combos[i].setCurrentIndex(ids.index(elem_id))
                self._combos[i].blockSignals(False)

            ovr_item = self._table.item(i, self._COL_OVR)
            if ovr_item is not None:
                ovr_item.setText(override)

        self._table.blockSignals(False)
        # Refresh all previews after loading
        for i in range(len(ENV_TEMPLATE)):
            self._update_preview(i)

    def _save_mapping(self) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Mapping", str(Path.home() / "env_mapping.json"),
                "JSON files (*.json);;All files (*)",
            )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._get_mapping(), f, indent=2)
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))

    def _export_env(self) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getSaveFileName(
                self, "Export .env", str(Path.home() / "profile.env"),
                "ENV files (*.env);;All files (*)",
            )
        if not path:
            return
        try:
            full_mapping = self._get_mapping()
            element_id_map = {k: v["element_id"] for k, v in full_mapping.items()}
            override_map   = {k: v["override"]    for k, v in full_mapping.items()}
            with open(path, "w", encoding="utf-8") as f:
                export_env(ENV_TEMPLATE, element_id_map, override_map, self._id_to_row, f)
            QMessageBox.information(self, "Export complete",
                                    f"Exported {len(ENV_TEMPLATE)} variables to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))


# ── ENV Compare Tab ───────────────────────────────────────────────────────────

class EnvCompareTab(QWidget):
    """Tab for comparing two .env files with color-coded diff view."""

    _COLS = ["Variable", "File 1 Value", "File 2 Value", "Status"]
    _COL_VAR, _COL_V1, _COL_V2, _COL_STATUS = range(4)
    _STATUS_COL_IDX = _COL_STATUS

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[EnvCompareRow] = []
        self._file_names: list[str] = ["File 1", "File 2"]
        self._build_ui()

    # ── construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # File picker rows
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        self._path_edit: list[QLineEdit] = []
        for i in range(2):
            n = i + 1
            lbl = QLabel(f".env File {n}:")
            edit = QLineEdit()
            edit.setPlaceholderText(f"Select .env file {n}…")
            edit.setReadOnly(True)
            browse = QPushButton("Browse…")
            browse.setFixedWidth(85)
            browse.clicked.connect(lambda _, idx=i: self._browse(idx))
            grid.addWidget(lbl,    i, 0)
            grid.addWidget(edit,   i, 1)
            grid.addWidget(browse, i, 2)
            self._path_edit.append(edit)

        self._compare_btn = QPushButton("⚡ Compare")
        self._compare_btn.setFixedWidth(110)
        self._compare_btn.setEnabled(False)
        self._compare_btn.clicked.connect(self._do_compare)
        grid.addWidget(self._compare_btn, 0, 3, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(grid)

        # Color filter bar (reuse same style as profile comparison)
        filter_bar, self._filter_group = _make_color_filter_bar()
        self._filter_group.idClicked.connect(self._on_color_filter)
        layout.addWidget(filter_bar)

        # Text filter
        text_row = QHBoxLayout()
        text_row.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search across all columns…")
        self._filter_edit.textChanged.connect(self._on_text_filter)
        text_row.addWidget(self._filter_edit)
        layout.addLayout(text_row)

        # Table
        self._model = _make_model(self._COLS)
        self._proxy = _StatusFilterProxy(status_col=EnvCompareTab._STATUS_COL_IDX)
        self._proxy.setSourceModel(self._model)
        self._table = _make_table()
        self._table.setModel(self._proxy)
        layout.addWidget(self._table)

        # Status + export bar
        bottom = QHBoxLayout()
        self._status_lbl = QLabel("")
        bottom.addWidget(self._status_lbl)
        bottom.addStretch()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setFixedWidth(120)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_csv)
        bottom.addWidget(self._export_btn)
        layout.addLayout(bottom)

    # ── slots ─────────────────────────────────────────────────────────────

    def _browse(self, idx: int) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getOpenFileName(
                self, f"Select .env File {idx + 1}",
                str(Path.home()),
                "ENV files (*.env);;All files (*)",
            )
        if path:
            self._path_edit[idx].setText(path)
            self._file_names[idx] = Path(path).name
            # Both paths filled → enable compare
            self._compare_btn.setEnabled(
                bool(self._path_edit[0].text() and self._path_edit[1].text())
            )

    def _do_compare(self) -> None:
        p1 = self._path_edit[0].text().strip()
        p2 = self._path_edit[1].text().strip()
        if not p1 or not p2:
            return
        try:
            env1 = parse_env_file(p1)
            env2 = parse_env_file(p2)
        except Exception as exc:
            QMessageBox.critical(self, "Parse error", str(exc))
            return

        self._rows = compare_env_files(env1, env2)
        self._fill_model()
        self._export_btn.setEnabled(True)

        counts = {s: 0 for s in STATUS_COLORS}
        for r in self._rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        self._status_lbl.setText(
            f"{counts['different']} different · "
            f"{counts['only_in_1']} only in F1 · "
            f"{counts['only_in_2']} only in F2 · "
            f"{counts['identical']} identical"
        )

    def _on_color_filter(self, btn_id: int) -> None:
        _, status, _ = FILTER_BUTTONS[btn_id]
        self._proxy.set_status(status)

    def _on_text_filter(self, text: str) -> None:
        self._proxy.set_text(text)

    def _export_csv(self) -> None:
        # Export visible (filtered) rows
        visible: list[EnvCompareRow] = []
        for proxy_row in range(self._proxy.rowCount()):
            src_row = self._proxy.mapToSource(self._proxy.index(proxy_row, 0)).row()
            visible.append(self._rows[src_row])

        with _suppress_glib_stderr():
            dest, _ = QFileDialog.getSaveFileName(
                self, "Export ENV Comparison",
                str(Path.home() / "env_comparison.csv"),
                "CSV files (*.csv);;All files (*)",
            )
        if not dest:
            return
        try:
            with open(dest, "w", newline="", encoding="utf-8") as f:
                export_env_comparison_csv(visible, f)
            QMessageBox.information(self, "Export complete",
                                    f"Exported {len(visible)} rows to:\n{dest}")
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))

    # ── helpers ───────────────────────────────────────────────────────────

    def _fill_model(self) -> None:
        # Update column headers with actual file names
        self._model.setHorizontalHeaderLabels([
            "Variable",
            self._file_names[0],
            self._file_names[1],
            "Status",
        ])
        self._model.setRowCount(0)
        for row in self._rows:
            color = STATUS_COLORS.get(row.status, QColor("white"))
            items = [
                QStandardItem(row.variable),
                QStandardItem(row.value_1),
                QStandardItem(row.value_2),
                QStandardItem(row.status),
            ]
            for item in items:
                item.setBackground(color)
            self._model.appendRow(items)


# ── MC Tab (all Mastercard profile functionality) ─────────────────────────────

class MCTab(QWidget):
    """Self-contained widget containing all Mastercard profile tooling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows_1: list[DataElementRow] = []
        self._rows_2: list[DataElementRow] = []
        self._cmp_rows: list[ComparisonRow] = []
        self._profile_names: list[str] = ["Profile 1", "Profile 2"]
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
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

        # Inner tabs
        self._tabs = QTabWidget()

        self._model_1 = _make_model(PROFILE_COLS)
        self._proxy_1 = _simple_proxy(self._model_1)
        self._table_1 = _make_table()
        self._table_1.setModel(self._proxy_1)
        self._tabs.addTab(self._table_1, "Profile 1")

        self._model_2 = _make_model(PROFILE_COLS)
        self._proxy_2 = _simple_proxy(self._model_2)
        self._table_2 = _make_table()
        self._table_2.setModel(self._proxy_2)
        self._tabs.addTab(self._table_2, "Profile 2")

        self._model_cmp = _make_model(CMP_COLS)
        self._proxy_cmp = _StatusFilterProxy(status_col=CMP_STATUS_COL)
        self._proxy_cmp.setSourceModel(self._model_cmp)
        self._table_cmp = _make_table()
        self._table_cmp.setModel(self._proxy_cmp)
        self._tabs.addTab(self._table_cmp, "⚡ Comparison")

        self._env_tab = EnvExportTab()
        self._tabs.addTab(self._env_tab, "⚙ ENV Export")

        vbox.addWidget(self._tabs)

        # Bottom bar (hidden on tabs that have their own controls)
        self._bottom_bar = QWidget()
        bottom = QHBoxLayout(self._bottom_bar)
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search across all columns…")
        self._filter_edit.textChanged.connect(self._on_filter_text)
        bottom.addWidget(self._filter_edit)
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setFixedWidth(120)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export)
        bottom.addWidget(self._export_btn)
        vbox.addWidget(self._bottom_bar)

        # Color filter / legend bar
        self._color_bar, self._filter_btn_group = _make_color_filter_bar()
        self._filter_btn_group.idClicked.connect(self._on_color_filter)
        vbox.addWidget(self._color_bar)

        # Status label
        self._status_lbl = QLabel("Ready — select two profiles and click Compare.")
        self._status_lbl.setStyleSheet("color: #555; padding: 2px 0;")
        vbox.addWidget(self._status_lbl)

        # Connect tab signal last (after all child widgets exist)
        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ── slots ─────────────────────────────────────────────────────────────

    def _browse(self, idx: int) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getOpenFileName(
                self, f"Select Profile {idx + 1}",
                str(Path.home()),
                "Profile files (*.profile);;All files (*)",
            )
        if path:
            self._path_edit[idx].setText(path)
            self._parse_btn[idx].setEnabled(True)
            self._clear_comparison()

    def _parse(self, idx: int) -> None:
        path = self._path_edit[idx].text().strip()
        if not path:
            return
        try:
            rows = parse_profile(path, include_empty=True)
        except Exception as exc:
            QMessageBox.critical(self, "Parse error", str(exc))
            return

        model = [self._model_1, self._model_2][idx]
        rows_attr = ["_rows_1", "_rows_2"][idx]
        setattr(self, rows_attr, rows)
        self._profile_names[idx] = Path(path).name
        self._fill_profile_model(model, rows)
        self._env_tab.update_profile(idx, rows)
        self._tabs.setCurrentIndex(idx)
        self._clear_comparison()
        self._export_btn.setEnabled(True)

        n_with_value = sum(1 for r in rows if r.value)
        self._status_lbl.setText(
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
        self._status_lbl.setText(
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
        rows = [r for r in rows if r.value]
        n = tab + 1
        dest = self._save_dialog(f"profile_{n}_export.csv")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8") as f:
            export_csv(rows, f)
        self._status_lbl.setText(f"Exported {len(rows)} rows → {dest}")

    def _export_comparison(self) -> None:
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
        self._status_lbl.setText(f"Exported {len(visible)} comparison rows → {dest}")

    def _on_filter_text(self, text: str) -> None:
        tab = self._tabs.currentIndex()
        if tab == TAB_P1:
            self._proxy_1.setFilterFixedString(text)
        elif tab == TAB_P2:
            self._proxy_2.setFilterFixedString(text)
        elif tab == TAB_CMP:
            self._proxy_cmp.set_text(text)

    def _on_color_filter(self, btn_id: int) -> None:
        _, status, _ = FILTER_BUTTONS[btn_id]
        self._proxy_cmp.set_status(status)
        self._tabs.setCurrentIndex(TAB_CMP)

    def _on_tab_changed(self, index: int) -> None:
        is_own_ui = index == TAB_ENV
        self._bottom_bar.setVisible(not is_own_ui)
        self._color_bar.setVisible(not is_own_ui)

        self._filter_edit.clear()
        if index != TAB_CMP:
            self._filter_btn_group.button(0).setChecked(True)
            self._proxy_cmp.set_status(None)

        has_data = (
            (index == TAB_P1  and bool(self._rows_1))
            or (index == TAB_P2  and bool(self._rows_2))
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
        headers = [
            self._profile_names[0] if col == "value_1"
            else self._profile_names[1] if col == "value_2"
            else col
            for col in CMP_COLS
        ]
        self._model_cmp.setHorizontalHeaderLabels(headers)
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
        self._filter_btn_group.button(0).setChecked(True)
        self._proxy_cmp.set_status(None)
        if self._tabs.currentIndex() == TAB_CMP:
            self._export_btn.setEnabled(False)

    def _save_dialog(self, default_name: str) -> str:
        with _suppress_glib_stderr():
            dest, _ = QFileDialog.getSaveFileName(
                self, "Export CSV",
                str(Path.home() / default_name),
                "CSV files (*.csv);;All files (*)",
            )
        return dest


# ── VISA ENV Export Tab ───────────────────────────────────────────────────────

def _visa_category_ok(category: str, prefix: str) -> bool:
    """Return True when a VISA element's category is compatible with the entry prefix."""
    if prefix == "eVsDef":
        return category != "qVSDC"          # Accept VSDC or VSDC & qVSDC
    if prefix == "eQvDef":
        return "qVSDC" in category          # Accept qVSDC or VSDC & qVSDC
    return True                             # Fixed entries — no filtering


class VisaEnvExportTab(QWidget):
    """ENV Export tab for VISA profiles — mirrors EnvExportTab for MC."""

    _ENV_COLS = ["ENV Variable", "Tag", "Tmpl Tag", "Prefix", "Profile Element", "Override Value", "Preview"]
    _COL_VAR, _COL_TAG, _COL_TTAG, _COL_PFX, _COL_ELEM, _COL_OVR, _COL_PREV = range(7)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_rows: list[list[VisaElementRow]] = [[], []]
        self._elem_options: list[tuple[str, str]] = []   # (id, label)
        self._id_to_row: dict[str, VisaElementRow] = {}
        self._combos: list[QComboBox] = []
        self._build_ui()

    # ── construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top bar
        top = QHBoxLayout()
        top.addWidget(QLabel("Source profile:"))
        self._src_combo = QComboBox()
        self._src_combo.addItems(["Profile 1", "Profile 2"])
        self._src_combo.setFixedWidth(110)
        self._src_combo.currentIndexChanged.connect(self._on_source_changed)
        top.addWidget(self._src_combo)
        top.addStretch()
        load_btn = QPushButton("Load Mapping…")
        load_btn.clicked.connect(self._load_mapping)
        save_btn = QPushButton("Save Mapping…")
        save_btn.clicked.connect(self._save_mapping)
        top.addWidget(load_btn)
        top.addWidget(save_btn)
        layout.addLayout(top)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search variable names, tags, values…")
        self._filter_edit.textChanged.connect(self._apply_filter)
        clr_btn = QPushButton("✕")
        clr_btn.setFixedWidth(28)
        clr_btn.setToolTip("Clear filter")
        clr_btn.clicked.connect(self._filter_edit.clear)
        filter_row.addWidget(self._filter_edit)
        filter_row.addWidget(clr_btn)
        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget(len(VISA_ENV_TEMPLATE), len(self._ENV_COLS))
        self._table.setHorizontalHeaderLabels(self._ENV_COLS)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self._COL_VAR,  QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self._COL_TAG,  QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_TTAG, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_PFX,  QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_ELEM, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(self._COL_OVR,  QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(self._COL_PREV, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(self._COL_ELEM, 300)
        self._table.setColumnWidth(self._COL_OVR,  180)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked |
                                    QTableWidget.EditTrigger.AnyKeyPressed)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)

        for row_idx, entry in enumerate(VISA_ENV_TEMPLATE):
            def _ro(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return item

            self._table.setItem(row_idx, self._COL_VAR,  _ro(entry.var_name))
            self._table.setItem(row_idx, self._COL_TAG,  _ro(entry.tag,          Qt.AlignmentFlag.AlignCenter))
            self._table.setItem(row_idx, self._COL_TTAG, _ro(entry.template_tag, Qt.AlignmentFlag.AlignCenter))
            self._table.setItem(row_idx, self._COL_PFX,  _ro(entry.prefix,       Qt.AlignmentFlag.AlignCenter))

            combo = QComboBox()
            combo.addItem(_NOT_MAPPED)
            combo.currentIndexChanged.connect(lambda _, r=row_idx: self._update_preview(r))
            self._combos.append(combo)
            self._table.setCellWidget(row_idx, self._COL_ELEM, combo)

            ovr_item = QTableWidgetItem(entry.default_value)
            ovr_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row_idx, self._COL_OVR, ovr_item)

            self._table.setItem(row_idx, self._COL_PREV, _ro("—"))

        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.addStretch()
        export_btn = QPushButton("Export .env…")
        export_btn.clicked.connect(self._export_env)
        bottom.addWidget(export_btn)
        layout.addLayout(bottom)

    # ── public API ────────────────────────────────────────────────────────

    def update_profile(self, idx: int, rows: list[VisaElementRow]) -> None:
        self._source_rows[idx] = rows
        if self._src_combo.currentIndex() == idx:
            self._on_source_changed(idx)

    # ── slots ─────────────────────────────────────────────────────────────

    def _on_source_changed(self, idx: int) -> None:
        rows = self._source_rows[idx]
        self._id_to_row = {_visa_elem_id(r): r for r in rows}
        self._elem_options = []
        for r in rows:
            eid = _visa_elem_id(r)
            tag_label = r.tag
            if r.template_tag:
                tag_label += f"/{r.template_tag}"
            label = f"{tag_label} — {r.name}  [{r.path}]"
            self._elem_options.append((eid, label))
        self._refresh_combos(keep_selection=False)

    def _apply_filter(self, text: str) -> None:
        low = text.lower()
        for row_idx in range(self._table.rowCount()):
            if not low:
                self._table.setRowHidden(row_idx, False)
                continue
            def _cell(col: int) -> str:
                item = self._table.item(row_idx, col)
                return item.text().lower() if item else ""
            combo = self._combos[row_idx] if row_idx < len(self._combos) else None
            combo_text = combo.currentText().lower() if combo else ""
            visible = (
                low in _cell(self._COL_VAR)
                or low in _cell(self._COL_TAG)
                or low in _cell(self._COL_TTAG)
                or low in _cell(self._COL_PFX)
                or low in _cell(self._COL_PREV)
                or low in _cell(self._COL_OVR)
                or low in combo_text
            )
            self._table.setRowHidden(row_idx, not visible)

    def _refresh_combos(self, *, keep_selection: bool) -> None:
        labels = [_NOT_MAPPED] + [label for _, label in self._elem_options]
        ids    = [""]          + [eid   for eid,  _   in self._elem_options]

        self._table.blockSignals(True)
        for row_idx, (combo, entry) in enumerate(zip(self._combos, VISA_ENV_TEMPLATE)):
            prev_id = combo.currentData() or ""
            combo.blockSignals(True)
            combo.clear()
            for label, eid in zip(labels, ids):
                combo.addItem(label, userData=eid)

            matched = False
            if keep_selection and prev_id and prev_id in ids:
                combo.setCurrentIndex(ids.index(prev_id))
                matched = True

            if not matched and entry.tag:
                for i, (eid, _) in enumerate(self._elem_options, start=1):
                    row = self._id_to_row.get(eid)
                    if not row or row.tag != entry.tag:
                        continue
                    if not _visa_category_ok(row.category, entry.prefix):
                        continue
                    # When the entry specifies a template_tag, require an exact match
                    if entry.template_tag and row.template_tag != entry.template_tag:
                        continue
                    combo.setCurrentIndex(i)
                    matched = True
                    break

            combo.blockSignals(False)

            if not keep_selection:
                ovr_item = self._table.item(row_idx, self._COL_OVR)
                if ovr_item is not None:
                    ovr_item.setText(entry.default_value)

        self._table.blockSignals(False)
        for row_idx in range(len(VISA_ENV_TEMPLATE)):
            self._update_preview(row_idx)

    def _update_preview(self, row_idx: int) -> None:
        from mc_profile_parser.parser import _hex_to_display
        combo = self._combos[row_idx]
        elem_id: str = combo.currentData() or ""
        entry = VISA_ENV_TEMPLATE[row_idx]

        ovr_item = self._table.item(row_idx, self._COL_OVR)
        override = ovr_item.text().strip() if ovr_item else ""

        if override:
            preview = override
        else:
            row = self._id_to_row.get(elem_id)
            hex_val = row.value if row else ""
            if hex_val and entry.decode_ascii:
                preview = _hex_to_display(hex_val, "a")
            else:
                preview = hex_val or "—"

        prev_item = self._table.item(row_idx, self._COL_PREV)
        if prev_item:
            self._table.blockSignals(True)
            prev_item.setText(preview)
            self._table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == self._COL_OVR:
            self._update_preview(item.row())

    def _get_mapping(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for i, (combo, entry) in enumerate(zip(self._combos, VISA_ENV_TEMPLATE)):
            elem_id = combo.currentData() or ""
            ovr_item = self._table.item(i, self._COL_OVR)
            override = ovr_item.text().strip() if ovr_item else ""
            result[entry.var_name] = {"element_id": elem_id, "override": override}
        return result

    def _load_mapping(self) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getOpenFileName(
                self, "Load VISA Mapping", str(Path.home()),
                "JSON files (*.json);;All files (*)",
            )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw: dict = json.load(f)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return

        ids = [""] + [eid for eid, _ in self._elem_options]
        self._table.blockSignals(True)
        for i, entry in enumerate(VISA_ENV_TEMPLATE):
            val = raw.get(entry.var_name)
            if val is None:
                continue
            elem_id = val if isinstance(val, str) else val.get("element_id", "")
            override = "" if isinstance(val, str) else val.get("override", "")
            if elem_id in ids:
                self._combos[i].blockSignals(True)
                self._combos[i].setCurrentIndex(ids.index(elem_id))
                self._combos[i].blockSignals(False)
            ovr_item = self._table.item(i, self._COL_OVR)
            if ovr_item is not None:
                ovr_item.setText(override)
        self._table.blockSignals(False)
        for i in range(len(VISA_ENV_TEMPLATE)):
            self._update_preview(i)

    def _save_mapping(self) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getSaveFileName(
                self, "Save VISA Mapping", str(Path.home() / "visa_env_mapping.json"),
                "JSON files (*.json);;All files (*)",
            )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._get_mapping(), f, indent=2)
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))

    def _export_env(self) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getSaveFileName(
                self, "Export VISA .env", str(Path.home() / "visa_profile.env"),
                "ENV files (*.env);;All files (*)",
            )
        if not path:
            return
        try:
            full = self._get_mapping()
            element_id_map = {k: v["element_id"] for k, v in full.items()}
            override_map   = {k: v["override"]    for k, v in full.items()}
            with open(path, "w", encoding="utf-8") as f:
                export_visa_env(VISA_ENV_TEMPLATE, element_id_map, override_map,
                                self._id_to_row, f)
            QMessageBox.information(self, "Export complete",
                                    f"Exported {len(VISA_ENV_TEMPLATE)} variables to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))


# ── VISA Tab ──────────────────────────────────────────────────────────────────

# Inner-tab indices for VisaTab
VISA_TAB_P1  = 0
VISA_TAB_P2  = 1
VISA_TAB_CMP = 2
VISA_TAB_ENV = 3


class VisaTab(QWidget):
    """Self-contained widget containing all VISA profile tooling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows_1: list[VisaElementRow] = []
        self._rows_2: list[VisaElementRow] = []
        self._cmp_rows: list[VisaComparisonRow] = []
        self._profile_names: list[str] = ["Profile 1", "Profile 2"]
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
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
            edit.setPlaceholderText(f"Select VISA XML profile {n}…")
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

        # Inner tabs
        self._tabs = QTabWidget()

        self._model_1 = _make_model(VISA_COLS)
        self._proxy_1 = _simple_proxy(self._model_1)
        t1 = _make_table()
        t1.setModel(self._proxy_1)
        self._tabs.addTab(t1, "Profile 1")

        self._model_2 = _make_model(VISA_COLS)
        self._proxy_2 = _simple_proxy(self._model_2)
        t2 = _make_table()
        t2.setModel(self._proxy_2)
        self._tabs.addTab(t2, "Profile 2")

        self._model_cmp = _make_model(VISA_CMP_COLS)
        self._proxy_cmp = _StatusFilterProxy(status_col=VISA_CMP_STATUS_COL)
        self._proxy_cmp.setSourceModel(self._model_cmp)
        t_cmp = _make_table()
        t_cmp.setModel(self._proxy_cmp)
        self._tabs.addTab(t_cmp, "⚡ Comparison")

        self._env_tab = VisaEnvExportTab()
        self._tabs.addTab(self._env_tab, "⚙ ENV Export")

        vbox.addWidget(self._tabs)

        # Bottom bar (hidden on ENV tab)
        self._bottom_bar = QWidget()
        bottom = QHBoxLayout(self._bottom_bar)
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search across all columns…")
        self._filter_edit.textChanged.connect(self._on_filter_text)
        bottom.addWidget(self._filter_edit)
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setFixedWidth(120)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export)
        bottom.addWidget(self._export_btn)
        vbox.addWidget(self._bottom_bar)

        # Color filter / legend bar
        self._color_bar, self._filter_btn_group = _make_color_filter_bar()
        self._filter_btn_group.idClicked.connect(self._on_color_filter)
        vbox.addWidget(self._color_bar)

        # Status label
        self._status_lbl = QLabel("Ready — select two VISA profiles and click Compare.")
        self._status_lbl.setStyleSheet("color: #555; padding: 2px 0;")
        vbox.addWidget(self._status_lbl)

        # Connect tab signal last
        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ── slots ─────────────────────────────────────────────────────────────

    def _browse(self, idx: int) -> None:
        with _suppress_glib_stderr():
            path, _ = QFileDialog.getOpenFileName(
                self, f"Select VISA Profile {idx + 1}",
                str(Path.home()),
                "XML files (*.xml);;All files (*)",
            )
        if path:
            self._path_edit[idx].setText(path)
            self._parse_btn[idx].setEnabled(True)
            self._clear_comparison()

    def _parse(self, idx: int) -> None:
        path = self._path_edit[idx].text().strip()
        if not path:
            return
        try:
            rows = parse_visa_profile(path, include_empty=True)
        except Exception as exc:
            QMessageBox.critical(self, "Parse error", str(exc))
            return

        model = [self._model_1, self._model_2][idx]
        rows_attr = ["_rows_1", "_rows_2"][idx]
        setattr(self, rows_attr, rows)
        self._profile_names[idx] = Path(path).name
        self._fill_profile_model(model, rows)
        self._env_tab.update_profile(idx, rows)
        self._tabs.setCurrentIndex(idx)
        self._clear_comparison()
        self._export_btn.setEnabled(True)

        n_with_value = sum(1 for r in rows if r.value)
        self._status_lbl.setText(
            f"Profile {idx + 1}: {len(rows)} elements parsed "
            f"({n_with_value} with non-empty value) — {Path(path).name}"
        )
        self._compare_btn.setEnabled(bool(self._rows_1 and self._rows_2))

    def _compare(self) -> None:
        if not self._rows_1 or not self._rows_2:
            return
        self._cmp_rows = compare_visa_profiles(self._rows_1, self._rows_2)
        self._fill_comparison_model(self._cmp_rows)
        self._tabs.setCurrentIndex(VISA_TAB_CMP)
        self._export_btn.setEnabled(True)

        counts = {s: 0 for s in STATUS_COLORS}
        for r in self._cmp_rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        self._status_lbl.setText(
            f"Comparison: {counts['different']} different · "
            f"{counts['only_in_1']} only in P1 · "
            f"{counts['only_in_2']} only in P2 · "
            f"{counts['identical']} identical"
        )

    def _export(self) -> None:
        tab = self._tabs.currentIndex()
        if tab == VISA_TAB_CMP:
            self._export_comparison()
        else:
            self._export_profile(tab)

    def _export_profile(self, tab: int) -> None:
        rows = self._rows_1 if tab == VISA_TAB_P1 else self._rows_2
        rows = [r for r in rows if r.value]
        n = tab + 1
        dest = self._save_dialog(f"visa_profile_{n}_export.csv")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8") as f:
            export_visa_csv(rows, f)
        self._status_lbl.setText(f"Exported {len(rows)} rows → {dest}")

    def _export_comparison(self) -> None:
        proxy = self._proxy_cmp
        visible: list[VisaComparisonRow] = []
        for proxy_row in range(proxy.rowCount()):
            src_row = proxy.mapToSource(proxy.index(proxy_row, 0)).row()
            visible.append(self._cmp_rows[src_row])
        dest = self._save_dialog("visa_comparison_export.csv")
        if not dest:
            return
        with open(dest, "w", newline="", encoding="utf-8") as f:
            export_visa_comparison_csv(visible, f)
        self._status_lbl.setText(f"Exported {len(visible)} comparison rows → {dest}")

    def _on_filter_text(self, text: str) -> None:
        tab = self._tabs.currentIndex()
        if tab == VISA_TAB_P1:
            self._proxy_1.setFilterFixedString(text)
        elif tab == VISA_TAB_P2:
            self._proxy_2.setFilterFixedString(text)
        elif tab == VISA_TAB_CMP:
            self._proxy_cmp.set_text(text)

    def _on_color_filter(self, btn_id: int) -> None:
        _, status, _ = FILTER_BUTTONS[btn_id]
        self._proxy_cmp.set_status(status)
        self._tabs.setCurrentIndex(VISA_TAB_CMP)

    def _on_tab_changed(self, index: int) -> None:
        is_env = index == VISA_TAB_ENV
        self._bottom_bar.setVisible(not is_env)
        self._color_bar.setVisible(not is_env)

        self._filter_edit.clear()
        if index != VISA_TAB_CMP:
            self._filter_btn_group.button(0).setChecked(True)
            self._proxy_cmp.set_status(None)

        has_data = (
            (index == VISA_TAB_P1  and bool(self._rows_1))
            or (index == VISA_TAB_P2  and bool(self._rows_2))
            or (index == VISA_TAB_CMP and bool(self._cmp_rows))
        )
        self._export_btn.setEnabled(has_data)

    # ── helpers ───────────────────────────────────────────────────────────

    def _fill_profile_model(self, model: QStandardItemModel,
                             rows: list[VisaElementRow]) -> None:
        model.setRowCount(0)
        for row in rows:
            items = [QStandardItem(str(getattr(row, col))) for col in VISA_COLS]
            model.appendRow(items)

    def _fill_comparison_model(self, rows: list[VisaComparisonRow]) -> None:
        headers = [
            self._profile_names[0] if col == "value_1"
            else self._profile_names[1] if col == "value_2"
            else col
            for col in VISA_CMP_COLS
        ]
        self._model_cmp.setHorizontalHeaderLabels(headers)
        self._model_cmp.setRowCount(0)
        for row in rows:
            color = STATUS_COLORS.get(row.status, QColor("white"))
            items: list[QStandardItem] = []
            for col in VISA_CMP_COLS:
                item = QStandardItem(str(getattr(row, col)))
                item.setBackground(color)
                items.append(item)
            self._model_cmp.appendRow(items)

    def _clear_comparison(self) -> None:
        self._cmp_rows = []
        self._model_cmp.setRowCount(0)
        self._filter_btn_group.button(0).setChecked(True)
        self._proxy_cmp.set_status(None)
        if self._tabs.currentIndex() == VISA_TAB_CMP:
            self._export_btn.setEnabled(False)

    def _save_dialog(self, default_name: str) -> str:
        with _suppress_glib_stderr():
            dest, _ = QFileDialog.getSaveFileName(
                self, "Export CSV",
                str(Path.home() / default_name),
                "CSV files (*.csv);;All files (*)",
            )
        return dest


# ── Main Window ───────────────────────────────────────────────────────────────

def _make_placeholder_tab(message: str) -> QWidget:
    w = QWidget()
    lbl = QLabel(message)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("font-size: 15px; color: #888; font-style: italic;")
    vbox = QVBoxLayout(w)
    vbox.addWidget(lbl)
    return w


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Card Profile Parser")
        self.resize(1200, 750)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        outer = QTabWidget()
        outer.setTabPosition(QTabWidget.TabPosition.North)
        outer.setDocumentMode(True)

        # ── MC tab ──
        self._mc_tab = MCTab()
        outer.addTab(self._mc_tab, "🏦  MC")

        # ── VISA tab ──
        self._visa_tab = VisaTab()
        outer.addTab(self._visa_tab, "💳  VISA")

        # ── ENV Compare tab (top-level, not card-scheme specific) ──
        outer.addTab(EnvCompareTab(), "🔀  ENV Compare")

        vbox.addWidget(outer)


def run_gui() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

