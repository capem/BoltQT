from __future__ import annotations
from typing import Callable, List
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt
import json
import os
from ..utils import ConfigManager
from ..utils.excel_manager import ExcelManager


class ConfigTab(QWidget):
    """Configuration tab for managing application settings."""

    def __init__(
        self,
        config_manager: ConfigManager,
        excel_manager: ExcelManager,
        error_handler: Callable[[Exception, str], None],
        status_handler: Callable[[str], None],
    ) -> None:
        super().__init__()

        self.config_manager = config_manager
        self.excel_manager = excel_manager
        self._handle_error = error_handler
        self._update_status = status_handler

        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll)

        # Create container widget for scroll area
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(20)
        scroll.setWidget(container)

        # Add configuration sections
        self._add_folder_section(container_layout)
        self._add_excel_section(container_layout)
        self._add_filter_section(container_layout)
        self._add_template_section(container_layout)
        self._add_preset_section(container_layout)
        self._add_save_section(container_layout)

        # Add stretch to bottom
        container_layout.addStretch()

        # Load initial values
        self._load_config()

        # Register for config changes
        self.config_manager.config_changed.connect(self._on_config_change)

    def _create_section_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled frame for a configuration section."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)

        if title:
            label = QLabel(title)
            label.setStyleSheet("font-weight: bold; font-size: 12pt;")
            layout.addWidget(label)

        return frame, layout

    def _add_folder_section(self, parent_layout: QVBoxLayout) -> None:
        """Add the folder configuration section."""
        frame, layout = self._create_section_frame("Folder Configuration")

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Source folder
        grid.addWidget(QLabel("Source Folder:"), 0, 0)
        self.source_folder_entry = QLineEdit()
        grid.addWidget(self.source_folder_entry, 0, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_folder("source_folder"))
        grid.addWidget(browse_btn, 0, 2)

        # Processed folder
        grid.addWidget(QLabel("Processed Folder:"), 1, 0)
        self.processed_folder_entry = QLineEdit()
        grid.addWidget(self.processed_folder_entry, 1, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_folder("processed_folder"))
        grid.addWidget(browse_btn, 1, 2)

        parent_layout.addWidget(frame)

    def _add_excel_section(self, parent_layout: QVBoxLayout) -> None:
        """Add the Excel configuration section."""
        frame, layout = self._create_section_frame("Excel Configuration")

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Excel file
        grid.addWidget(QLabel("Excel File:"), 0, 0)
        self.excel_file_entry = QLineEdit()
        grid.addWidget(self.excel_file_entry, 0, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_excel_file)
        grid.addWidget(browse_btn, 0, 2)

        # Excel sheet
        grid.addWidget(QLabel("Sheet Name:"), 1, 0)
        self.excel_sheet_combo = QComboBox()
        self.excel_sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
        self.excel_sheet_combo.setEnabled(False)  # Disabled until file selected
        grid.addWidget(self.excel_sheet_combo, 1, 1)

        parent_layout.addWidget(frame)

    def _add_filter_section(self, parent_layout: QVBoxLayout) -> None:
        """Add the filter configuration section."""
        frame, layout = self._create_section_frame("Filter Configuration")

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Filter columns
        self.filter_combos: List[QComboBox] = []
        for i in range(1, 5):
            grid.addWidget(QLabel(f"Filter {i} Column:"), i - 1, 0)
            combo = QComboBox()
            combo.setEnabled(False)  # Disabled until sheet selected
            self.filter_combos.append(combo)
            grid.addWidget(combo, i - 1, 1)

        parent_layout.addWidget(frame)

    def _on_sheet_changed(self, sheet_name: str) -> None:
        """Handle sheet selection change."""
        # Clear and disable filters if no sheet selected
        if not sheet_name:
            for combo in self.filter_combos:
                combo.clear()
                combo.setEnabled(False)
            return

        try:
            # Get current configuration to preserve filter values
            config = self.config_manager.get_config()
            stored_filter_values = [
                config.get(f"filter{i}_column", "")
                for i in range(1, len(self.filter_combos) + 1)
            ]

            # Get column names from selected sheet
            excel_file = self.excel_file_entry.text()
            columns = self.excel_manager.get_sheet_columns(excel_file, sheet_name)
            print(f"[DEBUG] Sheet changed to {sheet_name}, columns: {columns}")

            # Define default columns based on common names
            default_columns = {
                1: ["FOURNISSEURS", "FRS", "SUPPLIER"],  # Supplier column
                2: ["FACTURES", "FA", "INVOICE"],  # Invoice column
                3: ["DATE FACTURE", "DATE", "DATE FA"],  # Date column
                4: ["MNT DH", "MNT", "MONTANT", "AMOUNT"],  # Amount column
            }

            # Update filter combos with stored or default values
            for i, (combo, stored_value) in enumerate(
                zip(self.filter_combos, stored_filter_values), 1
            ):
                combo.blockSignals(True)
                try:
                    combo.clear()
                    combo.addItem("")  # Empty option
                    combo.addItems(columns)
                    combo.setEnabled(True)

                    # First try stored value
                    if stored_value and stored_value in columns:
                        print(
                            f"[DEBUG] Setting filter {i} to stored value: '{stored_value}'"
                        )
                        combo.setCurrentText(stored_value)
                    else:
                        # Try to find a matching default column
                        default_found = False
                        if i in default_columns:
                            for default_col in default_columns[i]:
                                if default_col in columns:
                                    print(
                                        f"[DEBUG] Setting filter {i} to default value: '{default_col}'"
                                    )
                                    combo.setCurrentText(default_col)
                                    default_found = True
                                    break

                        if not default_found:
                            print(f"[DEBUG] No matching value found for filter {i}")
                            combo.setCurrentIndex(0)
                finally:
                    combo.blockSignals(False)

            # Save configuration after setting defaults
            self._save_config()

        except Exception as e:
            print(f"[DEBUG] Error in sheet change: {str(e)}")
            self._handle_error(e, "loading sheet columns")
            # Disable filters on error
            for combo in self.filter_combos:
                combo.clear()
                combo.setEnabled(False)

    def _browse_excel_file(self) -> None:
        """Open file browser dialog for Excel files."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            try:
                print(f"[DEBUG] Selected new Excel file: {file_path}")

                # Clear all caches first
                self.excel_manager.clear_caches()

                # Update UI state
                self.excel_sheet_combo.clear()
                self.excel_sheet_combo.setEnabled(False)
                for combo in self.filter_combos:
                    combo.clear()
                    combo.setEnabled(False)

                # Update file path and load sheets
                self.excel_file_entry.setText(file_path)
                sheets = self.excel_manager.get_available_sheets(file_path)
                print(f"[DEBUG] Found sheets: {sheets}")

                if sheets:
                    # Update sheet combo
                    self.excel_sheet_combo.addItem("")
                    self.excel_sheet_combo.addItems(sheets)
                    self.excel_sheet_combo.setEnabled(True)
                    self._update_status(
                        f"Loaded Excel file: {os.path.basename(file_path)}"
                    )
                else:
                    self._update_status("No sheets found in Excel file")

                # Save configuration
                self._save_config()

            except Exception as e:
                print(f"[DEBUG] Error loading Excel file: {str(e)}")
                self._handle_error(e, "loading Excel file")

                # Reset UI state on error
                self.excel_manager.clear_caches()
                self.excel_sheet_combo.clear()
                self.excel_sheet_combo.setEnabled(False)
                for combo in self.filter_combos:
                    combo.clear()
                    combo.setEnabled(False)

    def _add_template_section(self, parent_layout: QVBoxLayout) -> None:
        """Add the output template configuration section."""
        frame, layout = self._create_section_frame("Output Template Configuration")

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Template field
        grid.addWidget(QLabel("Output Template:"), 0, 0)
        self.output_template_entry = QLineEdit()
        grid.addWidget(self.output_template_entry, 0, 1)

        # Help text
        help_label = QLabel(
            "Use ${field} for variable substitution, e.g. ${filter1}/${filter2}.pdf"
        )
        help_label.setStyleSheet("color: #666; font-style: italic;")
        grid.addWidget(help_label, 1, 0, 1, 2)

        parent_layout.addWidget(frame)

    def _add_preset_section(self, parent_layout: QVBoxLayout) -> None:
        """Add the preset configuration section."""
        frame, layout = self._create_section_frame("Preset Configuration")

        # Preset controls
        preset_layout = QHBoxLayout()
        layout.addLayout(preset_layout)

        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(200)
        preset_layout.addWidget(QLabel("Preset:"))
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()

        # Preset buttons
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)

        save_btn = QPushButton("Save Preset")
        save_btn.clicked.connect(self._save_preset)
        delete_btn = QPushButton("Delete Preset")
        delete_btn.clicked.connect(self._delete_preset)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()

        parent_layout.addWidget(frame)

        # Load presets
        self._load_presets()

    def _add_save_section(self, parent_layout: QVBoxLayout) -> None:
        """Add the save configuration section."""
        frame, layout = self._create_section_frame("")

        # Add save button
        save_btn = QPushButton("Save Configuration")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_btn.clicked.connect(self._save_config)
        layout.addWidget(save_btn)

        parent_layout.addWidget(frame)

    def _browse_folder(self, key: str) -> None:
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            entry = getattr(self, f"{key}_entry")
            entry.setText(folder)
            self._save_config()

    def _load_config(self) -> None:
        """Load configuration values into UI."""
        config = self.config_manager.get_config()

        # Update entry fields
        self.source_folder_entry.setText(config.get("source_folder", ""))
        self.processed_folder_entry.setText(config.get("processed_folder", ""))
        self.excel_file_entry.setText(config.get("excel_file", ""))
        self.output_template_entry.setText(config.get("output_template", ""))

        # Clear and disable combos initially
        self.excel_sheet_combo.clear()
        self.excel_sheet_combo.setEnabled(False)
        for combo in self.filter_combos:
            combo.clear()
            combo.setEnabled(False)

        # Load Excel file data if available
        excel_file = config.get("excel_file", "")
        if excel_file and os.path.exists(excel_file):
            try:
                # Clear caches to ensure fresh data
                self.excel_manager.clear_caches()

                # Load available sheets
                sheets = self.excel_manager.get_available_sheets(excel_file)

                # Update sheet combo
                self.excel_sheet_combo.addItem("")
                self.excel_sheet_combo.addItems(sheets)
                self.excel_sheet_combo.setEnabled(True)

                # Set selected sheet
                sheet_name = config.get("excel_sheet", "")
                if sheet_name in sheets:
                    # Temporarily block signals to prevent triggering _on_sheet_changed
                    self.excel_sheet_combo.blockSignals(True)
                    self.excel_sheet_combo.setCurrentText(sheet_name)
                    self.excel_sheet_combo.blockSignals(False)

                    # Load column names
                    try:
                        columns = self.excel_manager.get_sheet_columns(
                            excel_file, sheet_name
                        )
                        print(f"[DEBUG] Loaded columns: {columns}")

                        # Define default columns based on common names
                        default_columns = {
                            1: ["FOURNISSEURS", "FRS", "SUPPLIER"],  # Supplier column
                            2: ["FACTURES", "FA", "INVOICE"],  # Invoice column
                            3: ["DATE FACTURE", "DATE", "DATE FA"],  # Date column
                            4: ["MNT DH", "MNT", "MONTANT", "AMOUNT"],  # Amount column
                        }

                        # Update filter combos with columns and set values
                        for i, combo in enumerate(self.filter_combos, 1):
                            combo.blockSignals(True)
                            try:
                                combo.clear()
                                combo.addItem("")  # Empty option first
                                combo.addItems(columns)
                                combo.setEnabled(True)

                                # Try to set stored value first
                                stored_value = config.get(f"filter{i}_column", "")
                                print(
                                    f"[DEBUG] Filter {i} stored value: {stored_value}"
                                )

                                if stored_value and stored_value in columns:
                                    print(
                                        f"[DEBUG] Setting filter {i} to stored value: '{stored_value}'"
                                    )
                                    combo.setCurrentText(stored_value)
                                else:
                                    # If no stored value or invalid, try default values
                                    default_found = False
                                    if i in default_columns and not stored_value:
                                        for default_col in default_columns[i]:
                                            if default_col in columns:
                                                print(
                                                    f"[DEBUG] Setting filter {i} to default value: '{default_col}'"
                                                )
                                                combo.setCurrentText(default_col)
                                                default_found = True
                                                break

                                    if not default_found:
                                        print(
                                            f"[DEBUG] No matching value found for filter {i}"
                                        )
                                        combo.setCurrentIndex(0)
                            finally:
                                combo.blockSignals(False)

                    except Exception as e:
                        print(f"[DEBUG] Error updating filter combos: {str(e)}")
                        self._handle_error(e, "updating filter values")

            except Exception as e:
                self._handle_error(e, "loading Excel configuration")

    def _save_config(self) -> None:
        """Save configuration values from UI."""
        config = {
            "source_folder": self.source_folder_entry.text(),
            "processed_folder": self.processed_folder_entry.text(),
            "excel_file": self.excel_file_entry.text(),
            "excel_sheet": self.excel_sheet_combo.currentText(),
            "output_template": self.output_template_entry.text(),
        }

        # Add filter columns
        for i, combo in enumerate(self.filter_combos, 1):
            config[f"filter{i}_column"] = combo.currentText()

        self.config_manager.update_config(config)
        self._update_status("Configuration saved successfully")

    def _on_config_change(self) -> None:
        """Handle configuration changes."""
        self._load_config()

    def _load_presets(self) -> None:
        """Load presets from file."""
        try:
            if os.path.exists("presets.json"):
                with open("presets.json", "r", encoding="utf-8") as f:
                    presets = json.load(f)

                self.preset_combo.clear()
                self.preset_combo.addItem("Select Preset...")
                for name in presets:
                    self.preset_combo.addItem(name)

                self.preset_combo.currentIndexChanged.connect(self._load_preset)
        except Exception as e:
            self._handle_error(e, "loading presets")

    def _save_preset(self) -> None:
        """Save current configuration as a preset."""
        preset_name, ok = QFileDialog.getSaveFileName(
            self, "Save Preset", "", "Preset Files (*.json)"
        )
        if not ok or not preset_name:
            return

        try:
            config = self.config_manager.get_config()

            # Load existing presets
            presets = {}
            if os.path.exists("presets.json"):
                with open("presets.json", "r", encoding="utf-8") as f:
                    presets = json.load(f)

            # Add new preset
            preset_name = os.path.splitext(os.path.basename(preset_name))[0]
            presets[preset_name] = config

            # Save presets
            with open("presets.json", "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2)

            self._load_presets()
            self._update_status(f"Saved preset: {preset_name}")

        except Exception as e:
            self._handle_error(e, "saving preset")

    def _delete_preset(self) -> None:
        """Delete the selected preset."""
        preset_name = self.preset_combo.currentText()
        if preset_name == "Select Preset...":
            return

        try:
            if os.path.exists("presets.json"):
                with open("presets.json", "r", encoding="utf-8") as f:
                    presets = json.load(f)

                if preset_name in presets:
                    del presets[preset_name]

                    with open("presets.json", "w", encoding="utf-8") as f:
                        json.dump(presets, f, indent=2)

                    self._load_presets()
                    self._update_status(f"Deleted preset: {preset_name}")
        except Exception as e:
            self._handle_error(e, "deleting preset")

    def _load_preset(self) -> None:
        """Load the selected preset."""
        preset_name = self.preset_combo.currentText()
        if preset_name == "Select Preset...":
            return

        try:
            if os.path.exists("presets.json"):
                with open("presets.json", "r", encoding="utf-8") as f:
                    presets = json.load(f)

                if preset_name in presets:
                    self.config_manager.update_config(presets[preset_name])
                    self._update_status(f"Loaded preset: {preset_name}")
        except Exception as e:
            self._handle_error(e, "loading preset")
