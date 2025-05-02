from __future__ import annotations

import os
import traceback
from typing import Callable, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..utils import ConfigManager
from ..utils.excel_manager import ExcelManager
from ..utils.logger import get_logger


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
        self._error_handler = error_handler
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

        # Add preset section at the top
        self._add_preset_section(container_layout)
        
        # Add other configuration sections
        self._add_folder_section(container_layout)
        self._add_excel_section(container_layout)
        self._add_filter_section(container_layout)
        self._add_template_section(container_layout)
        self._add_vision_section(container_layout)
        
        # We removed the separate save section since saving will now be
        # integrated with the preset section

        # Add stretch to bottom
        container_layout.addStretch()

        # Load initial values
        self._load_config()

        # Register for config changes
        self.config_manager.config_changed.connect(self._load_config)

    def _create_section_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled frame for a configuration section."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        if title:
            # Create header layout to contain the title
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(
                0, 0, 0, 4
            )  # Reduced bottom margin for spacing

            # Create section title label with Mac-style font
            label = QLabel(title)
            label.setProperty("heading", "true")  # Used for styling in stylesheet
            label.setStyleSheet("""
                font-family: system-ui;
                font-weight: 600;
                font-size: 12pt;
                color: #000000;
                margin-bottom: 3px;
                background: transparent;
                border: none;
            """)
            header_layout.addWidget(label)

            # Add stretch to push the label to the left
            header_layout.addStretch()

            # Add the header to the main layout
            layout.addLayout(header_layout)

            # Add a subtle separator line below the title (optional)
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Plain)
            separator.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
            layout.addWidget(separator)

            # Add a smaller space after the separator
            layout.addSpacing(4)

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

        # Skip folder
        grid.addWidget(QLabel("Skip Folder:"), 2, 0)
        self.skip_folder_entry = QLineEdit()
        grid.addWidget(self.skip_folder_entry, 2, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_folder("skip_folder"))
        grid.addWidget(browse_btn, 2, 2)

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
            logger = get_logger()
            excel_file = self.excel_file_entry.text()
            columns = self.excel_manager.get_sheet_columns(excel_file, sheet_name)
            logger.debug(f"Sheet changed to {sheet_name}, columns: {columns}")

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
                        logger.debug(
                            f"Setting filter {i} to stored value: '{stored_value}'"
                        )
                        combo.setCurrentText(stored_value)
                    else:
                        # Try to find a matching default column
                        default_found = False
                        if i in default_columns:
                            for default_col in default_columns[i]:
                                if default_col in columns:
                                    logger.debug(
                                        f"Setting filter {i} to default value: '{default_col}'"
                                    )
                                    combo.setCurrentText(default_col)
                                    default_found = True
                                    break

                        if not default_found:
                            logger.debug(f"No matching value found for filter {i}")
                            combo.setCurrentIndex(0)
                finally:
                    combo.blockSignals(False)

            # Save configuration after setting defaults
            self._save_config()

        except Exception as e:
            logger = get_logger()
            logger.error(f"Error in sheet change: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            logger = get_logger()
            try:
                logger.debug(f"Selected new Excel file: {file_path}")

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
                logger.debug(f"Found sheets: {sheets}")

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
                logger.error(f"Error loading Excel file: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
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
        frame, layout = self._create_section_frame("Preset Management")

        # Current preset display at the top
        current_layout = QHBoxLayout()
        layout.addLayout(current_layout)

        # Label for active preset
        active_label = QLabel("<b>Active Preset:</b>")
        active_label.setStyleSheet("font-size: 11pt;")
        current_layout.addWidget(active_label)

        # Preset combo box
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(300)
        self.preset_combo.setToolTip("Select a preset to load")
        current_layout.addWidget(self.preset_combo)

        # Save to current preset button (replaces the old Save Configuration)
        save_current_btn = QPushButton("Save Preset")
        save_current_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_current_btn.setToolTip("Save changes to the currently selected preset")
        save_current_btn.clicked.connect(self._save_config)
        current_layout.addWidget(save_current_btn)
        
        # Spacer
        layout.addSpacing(10)
        
        # Preset management buttons
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)
        
        # Create new preset button (renamed from Save Preset)
        save_new_btn = QPushButton("Save As New Preset")
        save_new_btn.setToolTip("Save current configuration as a new preset")
        save_new_btn.clicked.connect(self._save_as_new_preset)
        
        # Delete preset button
        delete_btn = QPushButton("Delete Preset")
        delete_btn.setToolTip("Delete the currently selected preset")
        delete_btn.clicked.connect(self._delete_preset)
        
        # Add buttons to layout
        button_layout.addWidget(save_new_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()

        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setStyleSheet("background-color: #e0e0e0; max-height: 1px; margin-top: 5px; margin-bottom: 5px;")
        layout.addWidget(separator)

        parent_layout.addWidget(frame)

        # Load configs
        self._load_presets()

    def _add_vision_section(self, parent_layout: QVBoxLayout) -> None:
        """Add the vision configuration section."""
        frame, layout = self._create_section_frame("Vision Configuration")

        # Main vision settings
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Enabled checkbox
        self.vision_enabled_checkbox = QCheckBox("Enable Vision Processing")
        self.vision_enabled_checkbox.setToolTip(
            "Enable automatic document recognition and field auto-population"
        )
        grid.addWidget(self.vision_enabled_checkbox, 0, 0, 1, 2)

        # Document type - new field as part of the preset
        grid.addWidget(QLabel("Document Type:"), 1, 0)
        self.document_type_entry = QLineEdit()
        self.document_type_entry.setPlaceholderText(
            "Document type (e.g. Invoice, Order, Receipt)"
        )
        self.document_type_entry.setToolTip(
            "For reference only - identifies the document type this preset is for"
        )
        grid.addWidget(self.document_type_entry, 1, 1)

        # API Key
        grid.addWidget(QLabel("API Key:"), 2, 0)
        self.vision_api_key_entry = QLineEdit()
        self.vision_api_key_entry.setPlaceholderText("Enter Gemini API Key")
        self.vision_api_key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.vision_api_key_entry, 2, 1)

        # Model selection
        grid.addWidget(QLabel("Model:"), 3, 0)
        self.vision_model_combo = QComboBox()
        self.vision_model_combo.addItems(
            ["gemini-2.0-flash", "gemini-2.5-pro-exp-03-25"]
        )
        grid.addWidget(self.vision_model_combo, 3, 1)

        # Vision settings - condensed into main preset
        preset_vision_frame = QFrame()
        preset_vision_frame.setFrameStyle(
            QFrame.Shape.StyledPanel | QFrame.Shadow.Plain
        )
        preset_vision_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        preset_vision_layout = QVBoxLayout(preset_vision_frame)

        # Header for document settings
        doc_header_label = QLabel("Document Extraction Settings")
        doc_header_label.setStyleSheet("font-weight: bold;")
        preset_vision_layout.addWidget(doc_header_label)

        # Prompt template
        preset_vision_layout.addWidget(QLabel("Prompt Template:"))
        self.vision_prompt_text = QPlainTextEdit()
        self.vision_prompt_text.setMinimumHeight(150)
        self.vision_prompt_text.setPlaceholderText(
            "Enter prompt template for document extraction"
        )
        preset_vision_layout.addWidget(self.vision_prompt_text)

        # Field mappings
        preset_vision_layout.addWidget(QLabel("Field Mappings:"))
        mappings_frame = QFrame()
        mappings_layout = QGridLayout(mappings_frame)
        mappings_layout.setColumnStretch(1, 1)

        # Create field mapping entries
        self.vision_field_mappings = []
        for i in range(4):
            field_label = QLabel(f"Filter {i + 1}:")
            field_entry = QLineEdit()
            field_entry.setPlaceholderText(f"Field name mapped to filter{i + 1}")

            mappings_layout.addWidget(field_label, i, 0)
            mappings_layout.addWidget(field_entry, i, 1)

            self.vision_field_mappings.append(field_entry)

        preset_vision_layout.addWidget(mappings_frame)

        # Add preset vision frame to the main layout
        layout.addWidget(preset_vision_frame)

        # Add the frame to parent layout
        parent_layout.addWidget(frame)

    # This method has been removed as its functionality
    # is now integrated into the preset section

    def _browse_folder(self, key: str) -> None:
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            logger = get_logger()
            logger.debug(f"Selected {key} folder: {folder}")
            entry = getattr(self, f"{key}_entry")
            entry.setText(folder)
            self._save_config()

    def _load_config(self) -> None:
        """Load configuration into UI elements."""
        try:
            # Get current config
            config = self.config_manager.get_config()

            # Update entry fields
            self.source_folder_entry.setText(config.get("source_folder", ""))
            self.processed_folder_entry.setText(config.get("processed_folder", ""))
            self.skip_folder_entry.setText(config.get("skip_folder", ""))

            # Set excel file
            excel_path = config.get("excel_file", "")
            self.excel_file_entry.setText(excel_path)

            # Block signals to avoid triggering unnecessary updates
            self.excel_sheet_combo.blockSignals(True)
            self.excel_sheet_combo.clear()

            # Add sheet names
            sheet_names = self.excel_manager.get_available_sheets(excel_path)
            self.excel_sheet_combo.addItems(sheet_names)

            # Set selected sheet
            curr_sheet = config.get("excel_sheet", "")
            self.excel_sheet_combo.setCurrentText(curr_sheet)

            self.excel_sheet_combo.blockSignals(False)

            columns = self.excel_manager.get_sheet_columns(excel_path, curr_sheet)
            logger = get_logger()
            logger.debug(f"Loaded columns: {columns}")

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
                    logger.debug(f"Filter {i} stored value: {stored_value}")

                    logger.debug(
                        f"Setting filter {i} to stored value: '{stored_value}'"
                    )
                    combo.setCurrentText(stored_value)

                finally:
                    combo.blockSignals(False)

            # Set template
            self.output_template_entry.setText(config.get("output_template", ""))

            # Load vision settings
            vision_config = config.get("vision", {})
            self.vision_enabled_checkbox.setChecked(vision_config.get("enabled", False))
            self.vision_api_key_entry.setText(vision_config.get("gemini_api_key", ""))

            # Set model if available
            model = vision_config.get("model", "")
            if model and self.vision_model_combo.findText(model) != -1:
                self.vision_model_combo.setCurrentText(model)

            # Document type
            self.document_type_entry.setText(config.get("document_type", ""))

            # Load prompt and field mappings
            self.vision_prompt_text.setPlainText(config.get("prompt", ""))

            # Update field mappings
            field_mappings = config.get("field_mappings", {})
            for i, entry in enumerate(self.vision_field_mappings):
                filter_key = f"filter{i + 1}"
                # Find mapping that points to this filter
                mapping_value = ""
                for field, target in field_mappings.items():
                    if target == filter_key:
                        mapping_value = field
                        break

                entry.setText(mapping_value)

        except Exception as e:
            self._handle_error(e, "loading configuration")

    def _load_presets(self) -> None:
        """Load configs from config.json."""
        try:
            # Get preset names from the config manager
            preset_names = self.config_manager.get_preset_names()
            current_preset = self.config_manager.get_current_preset_name()

            # Update the preset combo box
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            self.preset_combo.addItem("Select Preset...")

            for name in preset_names:
                self.preset_combo.addItem(name)

            self.preset_combo.blockSignals(False)

            # Select current preset if available
            if current_preset and self.preset_combo.findText(current_preset) != -1:
                self.preset_combo.setCurrentText(current_preset)

            # Connect signal
            try:
                self.preset_combo.currentIndexChanged.disconnect()
            except TypeError:
                pass
            self.preset_combo.currentIndexChanged.connect(self._load_preset)

        except Exception as e:
            self._handle_error(e, "loading configs")

    def _load_preset(self) -> None:
        """Load the selected preset."""
        preset_name = self.preset_combo.currentText()
        if preset_name == "Select Preset...":
            return

        try:
            # Load the preset using the config manager
            self.config_manager.load_preset(preset_name)

            # Display status message
            self._update_status(f"Loaded preset: {preset_name}")

        except Exception as e:
            self._handle_error(e, "loading preset")

    def _save_as_new_preset(self) -> None:
        """Save current configuration as a new preset."""
        preset_name, ok = QFileDialog.getSaveFileName(
            self, "Save As New Preset", "", "Preset Files (*.json)"
        )
        if not ok or not preset_name:
            return

        try:
            # Extract base name without extension or path
            preset_name = os.path.splitext(os.path.basename(preset_name))[0]
            
            # Add "Preset: " prefix if not already present
            if not preset_name.startswith("Preset: "):
                preset_name = f"Preset: {preset_name}"

            # Save preset using the config manager
            self.config_manager.save_preset(preset_name)

            # Reload configs list
            self._load_presets()
            self._update_status(f"Saved as new preset: {preset_name}")

        except Exception as e:
            self._handle_error(e, "saving new preset")

    def _delete_preset(self) -> None:
        """Delete the selected preset."""
        preset_name = self.preset_combo.currentText()
        if preset_name == "Select Preset...":
            return

        try:
            # Delete preset using the config manager
            self.config_manager.delete_preset(preset_name)

            # Reload configs list
            self._load_presets()
            self._update_status(f"Deleted preset: {preset_name}")

        except Exception as e:
            self._handle_error(e, "deleting preset")

    def _save_config(self) -> None:
        """Save configuration values to the currently selected preset."""
        logger = get_logger()
        logger.debug("Saving configuration from UI to current preset")

        try:
            current_preset = self.config_manager.get_current_preset_name()
            logger.debug(f"Current preset: {current_preset}")
            # Check if a preset is currently selected
            if not current_preset:
                # No preset selected, ask user to select or create one
                logger.warning("No active preset selected")
                QMessageBox.warning(
                    self,
                    "No Active Preset",
                    "You need to select a preset first or create a new one.",
                    QMessageBox.StandardButton.Ok
                )
                return
                
            # Create update object with form values
            config = {
                "source_folder": self.source_folder_entry.text(),
                "processed_folder": self.processed_folder_entry.text(),
                "skip_folder": self.skip_folder_entry.text(),
                "excel_file": self.excel_file_entry.text(),
                "excel_sheet": self.excel_sheet_combo.currentText(),
                "output_template": self.output_template_entry.text(),
                "document_type": self.document_type_entry.text(),  # Document type from UI
            }
            logger.debug(f"Collected basic config values: {config}")

            # Add filter columns
            for i, combo in enumerate(self.filter_combos, 1):
                filter_value = combo.currentText()
                config[f"filter{i}_column"] = filter_value
                logger.debug(f"Filter {i} column: {filter_value}")

            # Get prompt text
            config["prompt"] = self.vision_prompt_text.toPlainText()
            logger.debug(f"Prompt length: {len(config['prompt'])} characters")

            # Get field mappings
            field_mappings = {}
            for i, entry in enumerate(self.vision_field_mappings):
                field_name = entry.text().strip()
                if field_name:
                    field_mappings[field_name] = f"filter{i + 1}"
                    logger.debug(f"Field mapping: {field_name} -> filter{i + 1}")

            # Add field mappings
            config["field_mappings"] = field_mappings

            # Get current vision config to preserve any settings not in the UI
            current_vision_config = self.config_manager.get_config().get("vision", {})

            # Create a new vision config with UI values
            vision_config = current_vision_config.copy()
            vision_config.update(
                {
                    "enabled": self.vision_enabled_checkbox.isChecked(),
                    "gemini_api_key": self.vision_api_key_entry.text(),
                    "model": self.vision_model_combo.currentText(),
                }
            )
            logger.debug(f"Vision config keys: {list(vision_config.keys())}")

            # Update with vision config
            config["vision"] = vision_config

            # Log the complete config we're about to save
            logger.debug(f"Saving config with keys: {list(config.keys())}")

            # Update the configuration
            self.config_manager.update_config(config)

            # Show status message
            self._update_status(f"Saved changes to preset: {current_preset}")
            logger.info(f"Successfully saved changes to preset: {current_preset}")

        except Exception as e:
            logger.error(f"Error saving preset: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._handle_error(e, "saving preset")

    def _show_warning(self, message: str) -> None:
        """Show a non-blocking warning to the user."""
        # Create message box with warning icon
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Warning")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Make it non-modal
        msg_box.setWindowModality(Qt.WindowModality.NonModal)

        # Show the message box
        msg_box.show()

        # Update status bar
        self._update_status(f"Warning: {message.split('\n')[0]}")

    def _handle_error(self, error: Exception, context: str) -> None:
        """Handle errors based on their severity."""
        # Log the error
        logger = get_logger()
        logger.error(f"Error {context}: {str(error)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Determine if this is a critical error that should show a blocking dialog
        is_critical = True

        # Non-critical errors:
        # 1. Excel file access errors
        if isinstance(error, OSError) and "excel" in context.lower():
            is_critical = False
            self._show_warning(f"Error {context}:\n{str(error)}")

        # 2. Loading sheet or columns errors
        elif "load" in context.lower() and (
            "sheet" in context.lower() or "column" in context.lower()
        ):
            is_critical = False
            self._show_warning(f"Error {context}:\n{str(error)}")

        # For critical errors, use the error handler
        if is_critical:
            self._error_handler(error, context)

        # Always update the status bar
        self._update_status(f"Error: {context}")
