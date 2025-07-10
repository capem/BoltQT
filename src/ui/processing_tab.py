from __future__ import annotations

import json
import os
import re
import time
import traceback
from datetime import datetime
from threading import Thread
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..utils import ConfigManager, ExcelManager, PDFManager, PDFTask
from ..utils.logger import get_logger
from ..utils.processing_thread import ProcessingThread
from ..utils.vision_manager import FuzzyMatcher, VisionManager
from .fuzzy_search import FuzzySearchFrame
from .loading_overlay import LoadingOverlay
from .pdf_viewer import PDFViewer
from .queue_display import QueueDisplay


# Create a signal relay object to safely pass signals from background threads to UI
class SignalRelay(QObject):
    """Signal relay for thread-safe communication."""

    vision_result_ready = pyqtSignal(object, str)  # vision_result, pdf_path


class ProcessingTab(QWidget):
    """Tab for processing PDF files."""

    _instance = None  # Class-level instance tracking

    @classmethod
    def get_instance(cls) -> Optional[ProcessingTab]:
        """Get the current ProcessingTab instance."""
        return cls._instance

    def __init__(
        self,
        config_manager: ConfigManager,
        excel_manager: ExcelManager,
        pdf_manager: PDFManager,
        vision_manager: VisionManager,
        error_handler: Callable[[Exception, str], None],
        status_handler: Callable[[str], None],
    ) -> None:
        super().__init__()
        ProcessingTab._instance = self

        # Store managers and handlers
        self.config_manager = config_manager
        self.excel_manager = excel_manager
        self.pdf_manager = pdf_manager
        self.vision_manager = vision_manager
        self._error_handler = error_handler
        self._update_status = status_handler

        # Initialize signal relay for thread-safe communication
        self.signal_relay = SignalRelay()
        self.signal_relay.vision_result_ready.connect(self._on_vision_result_ready)

        # Initialize fuzzy matcher
        self._fuzzy_matcher = FuzzyMatcher(config_manager)

        # Initialize state
        self._pending_config_change_id = None
        self._is_reloading = False
        self._is_applying_config = False  # Flag to prevent concurrent config changes
        self.current_pdf: Optional[str] = None
        self.current_pdf_start_time: Optional[datetime] = None
        self.filter_frames = []
        self._vision_mode = False  # Flag to indicate we're using vision results
        self.loading_overlay: LoadingOverlay | None = (
            None  # Added for loading indicator
        )

        # Initialize processing thread with managers
        self.processing_thread = ProcessingThread(
            config_manager=self.config_manager,
            excel_manager=self.excel_manager,
            pdf_manager=self.pdf_manager,
        )
        self.processing_thread.task_completed.connect(self._on_task_completed)
        self.processing_thread.task_failed.connect(self._on_task_failed)
        self.processing_thread.task_started.connect(self._on_task_started)
        self.processing_thread.start()

        # Create UI
        self._setup_ui()

        # Register for config changes
        self.config_manager.config_changed.connect(self._on_config_change)

    def _create_section_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled frame for a section."""
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
        layout.setContentsMargins(8, 8, 8, 8)  # Further reduced margins for compactness
        layout.setSpacing(4)  # Further reduced internal spacing

        if title:
            # Create header layout to contain the title
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(
                0, 0, 0, 2
            )  # Minimal bottom margin for compact headings

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

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)  # Minimized vertical margins
        layout.setSpacing(8)  # Reduced spacing

        # Create splitter for main panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)  # Thin handle for subtle appearance
        splitter.setChildrenCollapsible(False)  # Don't allow panels to collapse
        layout.addWidget(splitter)

        # Store reference to the main splitter
        self.main_splitter = splitter

        # Left panel (Filters and Actions)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)  # Reduced spacing between sections

        # Filters section
        filters_frame, filters_layout = self._create_section_frame("Filters")

        self.filters_container = QWidget()
        self.filters_layout = QVBoxLayout(self.filters_container)
        self.filters_layout.setContentsMargins(0, 0, 0, 0)  # Remove container margins
        self.filters_layout.setSpacing(6)  # Further reduce spacing between filters
        filters_layout.addWidget(self.filters_container)

        # Create the loading overlay, parented to the filters container
        self.loading_overlay = LoadingOverlay(self.filters_container)

        right_layout.addWidget(filters_frame)

        # Actions section (compact)
        actions_frame, actions_layout = self._create_section_frame("Actions")
        actions_layout.setSpacing(4)  # Further reduced spacing for more compact actions
        actions_frame.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )  # Prevent vertical expansion

        # Process button
        # Set up process button with fixed vertical size policy for compactness
        self.process_button = QPushButton("Process File")
        self.process_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.process_button.clicked.connect(self._process_current_file)
        self.process_button.setEnabled(False)
        # Make the process button the default button so it responds to Enter key press
        self.process_button.setDefault(True)
        self.process_button.setAutoDefault(True)
        # Add focus style
        self.process_button.setStyleSheet("""
            QPushButton {
                min-height: 22px;
                padding: 2px 8px;
                font-weight: 500;
            }
            QPushButton:default {
                background-color: #007aff;
                color: white;
                border: 1px solid #0062cc;
            }
            QPushButton:default:hover {
                background-color: #0069d9;
            }
        """)
        actions_layout.addWidget(self.process_button)

        # Skip button with dropdown menu
        self.skip_button = QPushButton("Skip File")
        self.skip_button.setStyleSheet("min-height: 22px; padding: 2px 8px;")
        self.skip_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        skip_menu = QMenu(self.skip_button)
        skip_in_place_action = skip_menu.addAction("Skip (Keep in Place)")
        skip_to_folder_action = skip_menu.addAction("Skip to Folder")
        skip_in_place_action.triggered.connect(
            lambda: self._skip_current_file("in_place")
        )
        skip_to_folder_action.triggered.connect(
            lambda: self._skip_current_file("to_folder")
        )
        self.skip_button.setMenu(skip_menu)
        actions_layout.addWidget(self.skip_button)

        # Vision button - For manual vision processing
        self.vision_button = QPushButton("Apply Vision")
        self.vision_button.clicked.connect(self._manual_vision_processing)
        self.vision_button.setStyleSheet("min-height: 22px; padding: 2px 8px;")
        self.vision_button.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        actions_layout.addWidget(self.vision_button)

        # Set initial vision button enabled state based on config
        config = self.config_manager.get_config()
        vision_enabled = config.get("vision", {}).get("enabled", False)
        self.vision_button.setEnabled(vision_enabled)
        if not vision_enabled:
            self.vision_button.setToolTip(
                "Vision processing is disabled in configuration"
            )
        else:
            self.vision_button.setToolTip(
                "Manually run vision processing on current PDF"
            )

        # Add actions frame with minimal margin
        right_layout.addWidget(actions_frame)

        # Use large stretch factor to push filters section to take more space
        right_layout.addStretch(10)

        # Center panel (PDF Viewer)
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)  # Minimal spacing

        # PDF viewer section
        viewer_frame, viewer_layout = self._create_section_frame("PDF Viewer")

        # PDF viewer
        self.pdf_viewer = PDFViewer(self.pdf_manager)
        viewer_layout.addWidget(self.pdf_viewer)

        center_layout.addWidget(viewer_frame)

        # Right panel (File Info and Queue)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)  # Minimal spacing

        # File Information section
        info_frame, info_layout = self._create_section_frame("File Information")

        # Create clickable label for file information
        self.file_info_label = QLabel("No file loaded")
        self.file_info_label.setStyleSheet("""
            QLabel {
                padding: 3px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QLabel:hover {
                background-color: #e9ecef;
                border-color: #ced4da;
            }
        """)
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        # Enable text elision for the label
        self.file_info_label.setTextFormat(Qt.TextFormat.PlainText)
        self.file_info_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_info_label.mousePressEvent = lambda e: self._select_pdf_file()
        info_layout.addWidget(self.file_info_label)

        left_layout.addWidget(info_frame)

        # Queue section
        queue_frame, queue_layout = self._create_section_frame("Processing Queue")

        # Queue display
        self.queue_display = QueueDisplay()
        self.queue_display.clear_button.clicked.connect(self._clear_completed)
        self.queue_display.retry_button.clicked.connect(self._retry_failed)
        queue_layout.addWidget(self.queue_display)

        left_layout.addWidget(queue_frame)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)

        # Set minimum widths to prevent panels from disappearing
        left_panel.setMinimumWidth(150)
        center_panel.setMinimumWidth(400)
        right_panel.setMinimumWidth(150)

        # Load initial data
        self._setup_filters()
        self._load_next_pdf()

        # Start periodic updates
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.start(500)  # Update every 500ms

        # Set splitter sizes AFTER Qt has initialized the layout
        QTimer.singleShot(0, lambda: splitter.setSizes([200, 600, 200]))

    def _setup_filters(self) -> None:
        """Setup filter controls based on configuration."""
        config = self.config_manager.get_config()

        # First, remove the stretch at the end if it exists
        # This prevents duplicate stretches when rebuilding filters
        for i in range(self.filters_layout.count()):
            item = self.filters_layout.itemAt(i)
            if item and item.spacerItem():
                # Found a stretch item, remove it
                self.filters_layout.removeItem(item)
                break

        # Clear existing filters - ensure proper cleanup
        for frame in self.filter_frames:
            # Remove from layout first
            self.filters_layout.removeWidget(frame["frame"])
            # Then delete the widget
            frame["frame"].setParent(None)
            frame["frame"].deleteLater()
        self.filter_frames.clear()

        # Process events to ensure widgets are properly removed
        QApplication.processEvents()

        # Create new filters
        i = 1
        while True:
            filter_key = f"filter{i}_column"
            if filter_key not in config:
                break

            column = config[filter_key]

            # Create frame and layout
            frame, layout = self._create_section_frame("")

            # Add label
            label = QLabel(column)
            label.setStyleSheet(
                "font-weight: bold; font-size: 9pt; margin: 0; padding: 0;"
            )
            label.setFixedHeight(16)  # Reduce label height
            layout.addWidget(label)

            # Create fuzzy search
            fuzzy = FuzzySearchFrame(
                identifier=f"processing_filter{i}",
                on_tab=lambda e, idx=i - 1: self._handle_filter_tab(e, idx),
            )
            # Connect value_selected signal to update dependent filters
            fuzzy.value_selected.connect(
                lambda idx=i - 1: self._on_filter_selected(idx)
            )
            # Connect text_changed signal to update process button state
            fuzzy.text_changed.connect(self._update_process_button)

            # Set tighter layout for fuzzy search frame
            fuzzy.setContentsMargins(0, 0, 0, 0)  # Remove all margins

            # Allow the fuzzy search frame to expand to fill available space
            fuzzy.setSizePolicy(
                self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy()
            )

            layout.addWidget(fuzzy)

            # Set ultra-compact margins for the filter frame
            frame.setContentsMargins(0, 0, 0, 0)  # Remove all margins
            layout.setContentsMargins(1, 1, 1, 1)  # Minimal margins
            layout.setSpacing(1)  # Minimal spacing within filter

            # Add to main layout
            self.filters_layout.addWidget(frame)

            # Store filter info
            self.filter_frames.append(
                {"frame": frame, "label": label, "fuzzy": fuzzy, "column": column}
            )

            i += 1

        # Add stretch at the end
        self.filters_layout.addStretch()

        # Load initial values for first filter
        if self.filter_frames:
            self._load_filter_values(0)

    def _format_filter2_value(
        self, value: str, row_idx: int
    ) -> str:  # Removed has_hyperlink param
        """Format filter2 value with row number and checkmark if hyperlinked (using cache)."""

        has_hyperlink = False
        # Check cache for hyperlink if filter 2 exists
        if len(self.filter_frames) > 1:
            filter2_column_name = self.filter_frames[1]["column"]
            config = self.config_manager.get_config()
            excel_file = config.get("excel_file")
            excel_sheet = config.get("excel_sheet")

            if excel_file and excel_sheet:
                # Get 0-based column index
                col_idx_0_based = self.excel_manager._get_column_index(
                    excel_file, excel_sheet, filter2_column_name
                )
                if col_idx_0_based is not None:
                    # Check cache using 0-based row and column indices
                    cached_link = self.excel_manager.get_hyperlink(
                        row_idx, col_idx_0_based
                    )
                    # --- Add Debug Log ---
                    logger = get_logger()
                    logger.debug(
                        f"FORMAT: row={row_idx}, col={col_idx_0_based} ('{filter2_column_name}'), cached_link='{cached_link}', has_hyperlink={bool(cached_link)}"
                    )
                    # --- End Debug Log ---
                    has_hyperlink = bool(cached_link)

        # Check if value already contains Excel Row information
        if re.search(r"⟨Excel Row[:-]\s*\d+⟩", value):
            # Already has Excel Row info, just add checkmark if needed
            if has_hyperlink and not value.startswith("✓ "):
                return "✓ " + value
            # Remove checkmark if hyperlink no longer exists
            if not has_hyperlink and value.startswith("✓ "):
                return value[2:]
            return value

        prefix = "✓ " if has_hyperlink else ""
        # +2 because Excel is 1-based and has header
        return f"{prefix}{value} ⟨Excel Row: {row_idx + 2}⟩"

    def _parse_filter2_value(self, formatted_value: str) -> tuple[str, int]:
        """Parse filter2 value to get original value and row number."""
        logger = get_logger()

        if not formatted_value:
            logger.debug("UI received empty filter2 value")
            return "", -1

        # Remove checkmark if present
        formatted_value = formatted_value.replace("✓ ", "", 1)
        match = re.match(r"(.*?)\s*⟨Excel Row:\s*(\d+)⟩", formatted_value)
        if match:
            value = match.group(1).strip()
            row_num = int(match.group(2))
            logger.debug(
                f"UI parsed filter2 value: '{formatted_value}' -> value='{value}', row_idx={row_num - 2}"
            )
            return value, row_num - 2  # Convert back to 0-based index

        logger.debug(f"UI failed to parse filter2 value: '{formatted_value}'")
        return formatted_value, -1

    def _load_filter_values(self, filter_index: int = 0) -> None:
        """Load values for a specific filter."""
        try:
            config = self.config_manager.get_config()
            if not (config["excel_file"] and config["excel_sheet"]):
                return

            # In vision mode, we still need to load filter values for fuzzy search functionality
            # The FuzzySearchFrame.set_values method will preserve the current value
            logger = get_logger()
            if self._vision_mode and filter_index > 0:
                logger.debug(
                    f"Loading filter values for filter {filter_index + 1} in vision mode (for fuzzy search)"
                )

            # Load Excel data if needed
            if self.excel_manager.excel_data is None:
                try:
                    self.excel_manager.load_excel_data(
                        config["excel_file"], config["excel_sheet"]
                    )
                except OSError as e:
                    # Handle file access error gracefully
                    logger = get_logger()
                    logger.error(f"Excel file access error: {str(e)}")
                    self._show_warning(
                        f"Could not access Excel file: {config['excel_file']}\n"
                        f"Error: {str(e)}\n"
                        f"Filters will not be populated."
                    )
                    # Set empty values for all filters
                    for i in range(len(self.filter_frames)):
                        self.filter_frames[i]["fuzzy"].set_values([])
                    return
                except Exception as e:
                    # Handle other Excel loading errors
                    logger = get_logger()
                    logger.error(f"Excel loading error: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    self._show_warning(
                        f"Error loading Excel data from {config['excel_file']}:\n"
                        f"{str(e)}\n"
                        f"Filters will not be populated."
                    )
                    # Set empty values for all filters
                    for i in range(len(self.filter_frames)):
                        self.filter_frames[i]["fuzzy"].set_values([])
                    return

            # If we have no filters, exit
            if not self.filter_frames or filter_index >= len(self.filter_frames):
                return

            # Get the dataframe
            df = self.excel_manager.excel_data

            # Track row_idx from filter2 if we have it
            row_idx = -1

            # Apply filters for all previous filters
            filtered_df = df.copy()
            for i in range(filter_index):
                # Skip if we don't have a value for this filter
                selected_value = self.filter_frames[i]["fuzzy"].get()
                if not selected_value:
                    continue

                # If this is filter2, parse it to get the clean value and row_idx
                if i == 1:
                    clean_value, parsed_row_idx = self._parse_filter2_value(
                        selected_value
                    )
                    selected_value = clean_value
                    row_idx = parsed_row_idx
                    logger = get_logger()
                    logger.debug(
                        f"Parsed filter2: value='{clean_value}', row_idx={row_idx}"
                    )
                # For filter3 and beyond, check row_idx
                if i > 1:
                    # Clear and return if no valid row_idx from filter2 (unless in vision mode)
                    if row_idx < 0 or row_idx not in filtered_df.index:
                        logger = get_logger()
                        if self._vision_mode:
                            logger.debug(
                                f"Invalid row_idx {row_idx} for filter {i + 1}, but continuing in vision mode"
                            )
                        else:
                            logger.debug(
                                f"No valid row_idx for filter {i + 1}, clearing all subsequent filters"
                            )
                            for idx in range(i, len(self.filter_frames)):
                                self.filter_frames[idx]["fuzzy"].clear()
                            return
                    else:
                        filtered_df = filtered_df.loc[[row_idx]]
                        logger.debug(f"Applied row_idx filter: {row_idx}")
                        break
                else:
                    # Apply standard column filter for filter1 and filter2
                    column = self.filter_frames[i]["column"]
                    filtered_df = filtered_df[
                        filtered_df[column].astype(str) == selected_value
                    ]

            # Get values for the current filter
            column = self.filter_frames[filter_index]["column"]

            # Special handling for filter2 - show ALL rows, not just unique values
            if filter_index == 1:
                # Hyperlinks are now pre-cached at startup or on config change.
                # No need to call cache_hyperlinks_for_column here anymore.

                # Get all rows from filtered_df, not just unique values
                formatted_values = []

                # Process each row individually
                for idx, row in filtered_df.iterrows():
                    value = str(row[column]).strip()
                    # Format using the updated method which checks the cache
                    formatted_value = self._format_filter2_value(value, idx)
                    formatted_values.append(formatted_value)

                # Sort the formatted values for better user experience
                formatted_values.sort()
                values = formatted_values
            else:
                # For filter3 and beyond, must have valid row_idx from filter2 (unless in vision mode)
                if filter_index > 1:
                    filter2_value = self.filter_frames[1]["fuzzy"].get()
                    logger = get_logger()
                    if not filter2_value:
                        logger.debug(
                            "No filter2 value selected, keeping subsequent filters empty"
                        )
                        return

                    _, row_idx = self._parse_filter2_value(filter2_value)
                    if row_idx < 0 or row_idx not in filtered_df.index:
                        if self._vision_mode:
                            logger.debug(
                                f"Invalid row_idx from filter2, but continuing in vision mode for filter {filter_index + 1}"
                            )
                        else:
                            logger.debug(
                                f"No valid row_idx from filter2, keeping filter {filter_index + 1} empty"
                            )
                            return

                    # Use only the specific row for valid row_idx
                    if row_idx >= 0 and row_idx in filtered_df.index:
                        filtered_df = filtered_df.loc[[row_idx]]
                        logger.debug(
                            f"Using row_idx {row_idx} for filter {filter_index + 1}"
                        )

                # Get unique values from filtered data
                values = sorted(filtered_df[column].astype(str).unique().tolist())

            # Update the fuzzy search values
            values = [str(x).strip() for x in values]

            # Format date values to dd/mm/yyyy format only if the column name contains "DATE"
            column_name = self.filter_frames[filter_index]["column"]
            logger = get_logger()
            logger.debug(
                f"Column name check: '{column_name}', contains 'DATE': {'DATE' in column_name.upper()}"
            )

            if "DATE" in column_name.upper():
                logger.debug(f"Formatting dates for column: {column_name}")
                formatted_values = []
                for value in values:
                    original_value = value
                    try:
                        # Check if the value could be parsed as a date
                        if "/" in value or "-" in value or "." in value:
                            formatted = False
                            # Try different date formats
                            for fmt in [
                                "%Y-%m-%d %H:%M:%S",  # For datetime with seconds: 2023-09-20 00:00:00
                                "%Y-%m-%d %H:%M",  # For datetime without seconds
                                "%Y/%m/%d %H:%M:%S",  # Other separators with time
                                "%Y/%m/%d %H:%M",
                                "%Y-%m-%d",  # Standard date formats
                                "%Y/%m/%d",
                                "%Y.%m.%d",
                                "%m/%d/%Y",
                                "%m-%d-%Y",
                                "%m.%d.%Y",
                                "%d/%m/%Y",
                                "%d-%m-%Y",
                                "%d.%m.%Y",
                            ]:
                                try:
                                    date_obj = datetime.strptime(value, fmt)
                                    # Format to dd/mm/yyyy
                                    new_value = date_obj.strftime("%d/%m/%Y")
                                    logger.debug(
                                        f"Date converted: '{value}' using format '{fmt}' -> '{new_value}'"
                                    )
                                    value = new_value
                                    formatted = True
                                    break
                                except ValueError:
                                    continue

                            if not formatted:
                                logger.debug(f"Could not parse date: '{value}'")
                    except Exception as e:
                        logger.error(f"Error parsing date '{value}': {str(e)}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        # If any error occurs during date parsing, keep the original value
                        pass

                    if original_value != value:
                        logger.debug(
                            f"Date formatting changed: '{original_value}' -> '{value}'"
                        )

                    formatted_values.append(value)

                logger.debug(f"Setting {len(formatted_values)} formatted date values")
                self.filter_frames[filter_index]["fuzzy"].set_values(formatted_values)
            else:
                # For non-date columns, use values as is
                logger.debug(
                    f"Using {len(values)} unformatted values for non-date column: {column_name}"
                )
                self.filter_frames[filter_index]["fuzzy"].set_values(values)

        except Exception as e:
            self._handle_error(
                e, f"loading filter values for filter {filter_index + 1}"
            )

    def _on_filter_selected(self, filter_index: int) -> None:
        """Handle selection in a filter."""
        # Update process button state
        self._update_process_button()

        # If this is the last filter, nothing to cascade
        if filter_index >= len(self.filter_frames) - 1:
            return

        # Clear all subsequent filters
        for i in range(filter_index + 1, len(self.filter_frames)):
            self.filter_frames[i]["fuzzy"].clear()

        # Update next filter's values
        self._load_filter_values(filter_index + 1)

    def _handle_filter_tab(self, _event: Any, filter_index: int) -> str:
        """Handle tab key in filter."""
        if filter_index < len(self.filter_frames) - 1:
            # Move to next filter
            self.filter_frames[filter_index + 1]["fuzzy"].entry.setFocus()
        else:
            # Move to process button and visually highlight it
            self.process_button.setFocus()
        return "break"

    def _process_current_file(self) -> None:
        """Process the current file with the selected filter values.

        This is the main PDF processing task, separate from vision preprocessing.
        Vision preprocessing may have happened earlier to populate the filters,
        but this is the actual processing task that will be tracked in the queue.
        """
        logger = get_logger()

        if not self.current_pdf:
            logger.info("Process attempted with no file selected")
            self._update_status("No file selected")
            return

        # Get filter values
        filter_values = []
        formatted_filter_values = []  # Store the original formatted values

        for i, frame in enumerate(self.filter_frames):
            value = frame["fuzzy"].get()
            if not value:
                logger.info(f"Process attempted with empty filter {i + 1}")
                self._update_status("All filters must be set")
                return

            # Store the original formatted value
            formatted_filter_values.append(value)

            # For filter2, extract the clean value without formatting
            if i == 1:
                clean_value, row_idx = self._parse_filter2_value(value)
                logger.debug(
                    f"Processing filter2 value: '{value}' -> clean='{clean_value}', row_idx={row_idx}"
                )
                value = clean_value

            filter_values.append(value)

        # Store the current PDF path before closing it
        current_pdf_path = self.current_pdf
        logger.info(f"Processing file: {current_pdf_path}")

        # Clear the PDF from the viewer to release file handles
        self.pdf_viewer.clear_pdf()

        # Create PDF processing task (not to be confused with vision preprocessing)
        task = PDFTask(
            pdf_path=current_pdf_path,
            filter_values=filter_values,
            start_time=datetime.now(),
        )

        # Store the row index if we have it
        if len(formatted_filter_values) > 1:
            _, row_idx = self._parse_filter2_value(formatted_filter_values[1])
            if row_idx >= 0:
                task.row_idx = row_idx
                logger.debug(
                    f"Pre-setting task row_idx to {row_idx} from filter2 value"
                )

        # Add to processing queue
        self.processing_thread.tasks[task.task_id] = task

        logger.info(
            f"Added PDF processing task {task.task_id} to queue with filter values: {filter_values}"
        )

        # Immediately update the UI to show the new task
        self._update_display()

        # Reset all fuzzy search inputs
        for frame in self.filter_frames:
            frame["fuzzy"].clear()

        # Load next file
        self._load_next_pdf()

    def _select_pdf_file(self) -> None:
        """Handle manual PDF file selection."""
        try:
            config = self.config_manager.get_config()
            source_folder = config.get("source_folder", "")

            if not source_folder:
                self._handle_error(
                    ValueError("Source folder not configured"), "selecting PDF file"
                )
                return

            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select PDF File", source_folder, "PDF Files (*.pdf)"
            )

            if file_path:
                # Close current PDF
                if self.current_pdf:
                    self.pdf_viewer.clear_pdf()
                    self.current_pdf = None
                    self.current_pdf_start_time = None

                # Load the selected PDF
                self.current_pdf = file_path
                self.current_pdf_start_time = datetime.now()
                self.pdf_viewer.display_pdf(file_path)

                # Update file info label
                self._update_file_info_label(file_path)

                # Refresh Excel data
                excel_file = config.get("excel_file")
                excel_sheet = config.get("excel_sheet")
                if excel_file and excel_sheet:
                    self.excel_manager.load_excel_data(excel_file, excel_sheet)

                # Clear and update filters
                for frame in self.filter_frames:
                    frame["fuzzy"].clear()
                self._load_filter_values()

                # Focus first filter
                if self.filter_frames:
                    self.filter_frames[0]["fuzzy"].entry.setFocus()

                self._update_status("Ready")
                self._update_process_button()

        except Exception as e:
            self._handle_error(e, "selecting PDF file")

    def _update_file_info_label(self, file_path: Optional[str] = None) -> None:
        """Update the file information label with the current or specified file."""
        if file_path:
            file_name = os.path.basename(file_path)
            self.file_info_label.setText(f"File: {file_name}")
            # Set tooltip to show full path on hover
            self.file_info_label.setToolTip(file_path)

            # Force the label to update its size and layout
            def update_layout():
                # First adjust the label's size
                self.file_info_label.adjustSize()
                # Then force the parent layout to update
                parent_layout = self.file_info_label.parent().layout()
                if parent_layout:
                    parent_layout.activate()
                    parent_layout.update()
                # Also update the parent widget
                self.file_info_label.parent().adjustSize()
                # Process events to ensure UI updates immediately
                QApplication.processEvents()

            # Use a timer to ensure this happens after the current event cycle
            QTimer.singleShot(0, update_layout)
        else:
            self.file_info_label.setText("No file loaded")
            self.file_info_label.setToolTip("")

    def _skip_current_file(self, skip_type: str) -> None:
        """Skip the current file using the selected skip type."""
        logger = get_logger()

        if not self.current_pdf:
            logger.info("Skip attempted with no file selected")
            self._update_status("No file selected to skip")
            return

        # Store current PDF path before clearing it
        current_pdf_path = self.current_pdf
        current_pdf_start_time = self.current_pdf_start_time or datetime.now()

        logger.info(f"Skipping file: {current_pdf_path} with skip type: {skip_type}")

        # First clear the PDF from the viewer to release file handles
        logger.debug(f"Clearing PDF viewer before skipping file: {current_pdf_path}")
        self.pdf_viewer.clear_pdf()

        # Reset state variables
        self.current_pdf = None
        self.current_pdf_start_time = None
        self._update_file_info_label()

        # Process events to ensure file handles are released
        QApplication.processEvents()

        # Now handle the skip operation
        config = self.config_manager.get_config()
        skipped_path = current_pdf_path

        if skip_type == "to_folder":
            skip_folder = config.get("skip_folder", "")
            if not skip_folder:
                logger.warning("Skip folder not configured in settings")
                QMessageBox.warning(
                    self,
                    "Skip Folder Not Set",
                    "No skip folder is configured in settings.",
                )
                return

            logger.debug(f"Attempting to move skipped PDF to folder: {skip_folder}")
            # Try to move the file
            result = self.pdf_manager.move_skipped_pdf_to_folder(
                current_pdf_path, skip_folder
            )

            if result is None:
                # Failed to move the file - create a failed task instead of a skipped task
                logger.error(f"Failed to move file to skip folder: {current_pdf_path}")
                self._update_status(
                    "Failed to move file to skip folder. File marked as failed."
                )

                # Create failed task
                task = PDFTask(
                    pdf_path=current_pdf_path,
                    status="failed",
                    start_time=current_pdf_start_time,
                    end_time=datetime.now(),
                    error_msg="Could not move file to skip folder - file may be locked",
                )
                self.processing_thread.tasks[task.task_id] = task
                logger.info(
                    f"Created failed task {task.task_id} for file that couldn't be moved"
                )

                # Load next PDF and return
                self._load_next_pdf()
                return

            # If we get here, the move was successful
            skipped_path = result
            logger.info(f"Successfully moved file to skip folder: {skipped_path}")
            self._update_status("File skipped and moved to skip folder.")
        else:
            # For in-place skipping, just mark the file as processed
            logger.info(f"Skipping file in place: {current_pdf_path}")
            self.pdf_manager.mark_file_processed(current_pdf_path)

        # Create skipped task for tracking
        task = PDFTask(
            pdf_path=skipped_path,
            status="skipped",
            start_time=current_pdf_start_time,
            end_time=datetime.now(),
            skip_type=skip_type,
        )
        self.processing_thread.tasks[task.task_id] = task
        logger.info(f"Created skipped task {task.task_id} for {skipped_path}")

        # Immediately update the UI to show the new skipped task
        self._update_display()

        # Load next PDF
        self._load_next_pdf()

    def _load_next_pdf(self, _skip: bool = False) -> None:
        """Load the next PDF file and optionally start vision preprocessing.

        This handles file loading, cleanup, and initiates vision preprocessing
        for filter auto-population, which is separate from the actual PDF processing.
        """
        logger = get_logger()
        try:
            logger.debug(f"Loading next PDF, current_pdf={self.current_pdf}")

            # Ensure proper cleanup of current PDF
            if self.current_pdf:
                try:
                    # Clear the PDF from the viewer with retries
                    retry_count = 3
                    for attempt in range(retry_count):
                        try:
                            self.pdf_viewer.clear_pdf()
                            break
                        except Exception as e:
                            if attempt < retry_count - 1:
                                logger.debug(
                                    f"Retry {attempt + 1}: Error clearing PDF: {str(e)}"
                                )
                                time.sleep(0.5)  # Short delay between retries
                                continue
                            raise

                    # Reset state variables and update UI
                    self.current_pdf = None
                    self.current_pdf_start_time = None
                    self._update_file_info_label()

                except Exception as cleanup_error:
                    logger.warning(f"Error during PDF cleanup: {str(cleanup_error)}")
                    # Continue even if cleanup fails

            # Get config and validate
            config = self.config_manager.get_config()
            if not config["source_folder"]:
                self._update_status("Source folder not configured")
                return

            # Get active tasks - only consider PDF processing tasks, not vision preprocessing
            active_tasks = {
                k: v
                for k, v in self.processing_thread.tasks.items()
                if v.status in ["pending", "processing"]
            }

            # Allow events to process before loading next PDF
            QApplication.processEvents()

            # Try to get next PDF with retries
            next_pdf = None
            retry_count = 3
            for attempt in range(retry_count):
                try:
                    next_pdf = self.pdf_manager.get_next_pdf(
                        config["source_folder"], active_tasks
                    )
                    break
                except Exception as e:
                    if attempt < retry_count - 1:
                        logger.debug(
                            f"Retry {attempt + 1}: Error getting next PDF: {str(e)}"
                        )
                        time.sleep(0.5)
                        continue
                    raise

            if next_pdf:
                logger.info(f"Loading next PDF: {next_pdf}")
                self.current_pdf = next_pdf
                self.current_pdf_start_time = datetime.now()

                # Update file info label
                self._update_file_info_label(next_pdf)

                # Display PDF with retries built into the display_pdf method
                self.pdf_viewer.display_pdf(next_pdf, retry_count=3)

                # Clear and update filters
                for frame in self.filter_frames:
                    frame["fuzzy"].clear()
                self._load_filter_values()

                # Start vision preprocessing for auto-population, separate from PDF processing task
                logger.debug(
                    f"Initiating vision preprocessing to auto-populate filters for {next_pdf}"
                )
                self._start_vision_processing(next_pdf)

                # Focus first filter
                if self.filter_frames:
                    self.filter_frames[0]["fuzzy"].entry.setFocus()

                self._update_status("Ready")
            else:
                logger.info("No more PDF files to process")
                self.current_pdf = None
                self.current_pdf_start_time = None
                self.pdf_viewer.display_pdf(None)
                self._update_status("No files to process")

                if self.filter_frames:
                    self.filter_frames[0]["fuzzy"].entry.setFocus()

            # Update UI state
            self._update_process_button()

        except Exception as e:
            self._handle_error(e, "loading next PDF")
            # Try to recover by clearing the current PDF
            self.current_pdf = None
            self.current_pdf_start_time = None
            self.pdf_viewer.display_pdf(None)

    def _start_vision_processing(self, pdf_path: str) -> None:
        """Start vision processing for a PDF to enable auto-population of filters.

        This is separate from the main PDF processing tasks and is only used
        to help populate form fields before the actual PDF processing begins.
        """
        logger = get_logger()
        try:
            # Check if vision processing is enabled
            # Note: is_vision_enabled() will log the specific reason for being disabled
            if not self.vision_manager.is_vision_enabled():
                logger.debug("Vision processing is disabled, skipping preprocessing")
                return

            logger.info(f"Starting vision preprocessing for {pdf_path}")

            # --- Show Loading Overlay and Disable Filters ---
            if self.loading_overlay:
                self.loading_overlay.show()
            for frame_info in self.filter_frames:
                frame_info["fuzzy"].setEnabled(False)
            QApplication.processEvents()  # Ensure overlay and disabled state are visible

            # Create background thread for vision preprocessing

            def process_vision():
                try:
                    # Use the vision manager directly to preprocess the PDF
                    vision_result = self.vision_manager.preprocess_pdf(pdf_path)

                    if vision_result:
                        logger.info(f"Vision preprocessing completed for {pdf_path}")
                        logger.debug(
                            f"Vision result keys: {list(vision_result.keys())}"
                        )

                        # Emit signal to apply vision results in the main thread
                        logger.debug(
                            "Emitting vision_result_ready signal to main thread"
                        )
                        self.signal_relay.vision_result_ready.emit(
                            vision_result, pdf_path
                        )
                    else:
                        logger.warning(
                            f"Vision preprocessing failed or is disabled for {pdf_path}"
                        )

                except Exception as e:
                    logger.error(f"Error in vision preprocessing thread: {str(e)}")
                    logger.error(f"Error traceback: {traceback.format_exc()}")

            # Start background thread for vision preprocessing
            vision_thread = Thread(target=process_vision)
            vision_thread.daemon = True  # Make thread exit when main thread exits
            vision_thread.start()

        except Exception as e:
            logger.error(f"Error starting vision preprocessing: {str(e)}")
            logger.error(f"Error traceback: {traceback.format_exc()}")

    def _on_vision_result_ready(self, vision_result: dict, pdf_path: str) -> None:
        """Handle vision results from background thread in the main thread.

        This handles the auto-population of filters based on vision results,
        separate from the actual PDF processing tasks.
        """
        logger = get_logger()
        try:
            # --- Hide Loading Overlay and Re-enable Filters ---
            # This runs when the signal arrives, regardless of success/failure in the thread
            if self.loading_overlay:
                self.loading_overlay.hide()
            for frame_info in self.filter_frames:
                # Re-enable all filters. Subsequent logic might disable some based on selections.
                frame_info["fuzzy"].setEnabled(True)
            QApplication.processEvents()  # Ensure UI updates

            logger.debug(f"Vision preprocessing result ready for {pdf_path}")

            # Check if this is still the current PDF
            if not self.current_pdf or not self.pdf_manager._paths_equal(
                self.current_pdf, pdf_path
            ):
                logger.warning(
                    f"PDF has changed, not applying vision results (current: {self.current_pdf}, received: {pdf_path})"
                )
                return

            # Apply the vision results to populate filters
            self._apply_vision_result(vision_result)
        except Exception as e:
            logger.error(f"Error handling vision result: {str(e)}")
            logger.error(f"Error traceback: {traceback.format_exc()}")

    def _apply_vision_result(self, vision_result: dict) -> None:
        """Apply vision preprocessing results to populate filter fields.

        This method handles the auto-population of filter fields based on vision
        preprocessing results. This is entirely separate from the actual PDF processing
        task and happens before the user clicks 'Process File'.
        """
        logger = get_logger()
        try:
            logger.info("Applying vision preprocessing results to filters")

            if not vision_result:
                logger.warning("No vision preprocessing result to apply")
                return

            logger.debug(
                f"Vision preprocessing result keys: {list(vision_result.keys())}"
            )

            # Enable vision mode to bypass row validation during filter population
            # This is only for the filter population phase and not for actual processing
            self._vision_mode = True
            logger.debug(
                "Enabling vision mode to bypass row validation for filter population"
            )

            # Use normalized data if available (new approach), otherwise fall back to extracted_data (backward compatibility)
            normalized_data = vision_result.get("normalized_data", {})

            # Clear all filters before setting new values
            for frame in self.filter_frames:
                frame["fuzzy"].clear()

            logger.debug(
                f"Using normalized data for filter population: {json.dumps(normalized_data, indent=2)}"
            )

            # Process filters in order (filter1, filter2, filter3, etc.) rather than in dictionary order
            # This ensures proper cascading of filter values
            for i in range(len(self.filter_frames)):
                filter_key = f"filter{i+1}"

                # Skip if this filter isn't in the normalized data
                if filter_key not in normalized_data:
                    logger.debug(f"{filter_key} not found in vision results, skipping")
                    continue

                filter_value = normalized_data[filter_key]
                if not filter_value:
                    # Skip empty values
                    logger.debug(f"{filter_key} has empty value, skipping")
                    continue

                # Convert filter1 to index 0, etc.
                filter_index = i  # We're already iterating in order

                logger.debug(
                    f"Setting {filter_key} (index {filter_index}) to '{filter_value}'"
                )

                # For filter1, set value and trigger cascade to populate subsequent filter values
                if filter_index == 0:
                    # Set the value
                    self.filter_frames[filter_index]["fuzzy"].set(str(filter_value))

                    # Trigger filter cascade to populate filter2 values
                    self._on_filter_selected(filter_index)

                    # Process events to ensure UI updates before continuing
                    QApplication.processEvents()

                    # Skip the default setting at the end of the loop since we've already set it
                    continue
                # For all other filters (filter2, filter3, filter4, etc.), try to find a matching value using fuzzy_frames
                else:
                    # Get available values for this filter
                    available_values = self._get_available_filter_values(filter_index)
                    logger.debug(
                        f"Available values for filter{filter_index + 1}: {len(available_values)}"
                    )

                    if available_values:
                        filter_value_str = str(filter_value).strip()

                        # Update the fuzzy frame with available values
                        fuzzy_frame = self.filter_frames[filter_index]["fuzzy"]
                        fuzzy_frame.all_values = available_values

                        # Set the value to trigger fuzzy search
                        fuzzy_frame.set(filter_value_str)

                        # Force update of the listbox to get matches
                        fuzzy_frame._update_listbox()

                        # Check if we have any matches
                        if fuzzy_frame.listbox.count() > 0:
                            # Get the top match (first item in the listbox)
                            top_match = fuzzy_frame.listbox.item(0).text()
                            logger.debug(
                                f"Found fuzzy match for filter{filter_index + 1} using fuzzy_frames: '{top_match}'"
                            )
                            fuzzy_frame.set(top_match)

                            # If this isn't the last filter, trigger cascade to populate next filter
                            if filter_index < len(self.filter_frames) - 1:
                                self._on_filter_selected(filter_index)
                                QApplication.processEvents()
                        else:
                            # No matches found, keep the original value
                            logger.debug(
                                f"No match found for filter{filter_index + 1} '{filter_value_str}' in Excel using fuzzy_frames"
                            )
                            fuzzy_frame.set(filter_value_str)
                    else:
                        # No available values, set directly
                        logger.debug(
                            f"No available values for filter{filter_index + 1}, setting directly: '{filter_value}'"
                        )
                        self.filter_frames[filter_index]["fuzzy"].set(str(filter_value))

                # Update UI after each filter
                QApplication.processEvents()

            # Update process button state
            self._update_process_button()

            # Now load filter values for all filters to ensure proper filtering
            # This will populate the dropdown lists with the correct filtered values
            # based on the current filter selections from vision
            logger.debug("Loading filter values for all filters after vision auto-population")
            for i in range(len(self.filter_frames)):
                self._load_filter_values(i)

            logger.info("Successfully applied vision preprocessing results to filters")

            # Disable vision mode after applying all values
            self._vision_mode = False
            logger.debug("Disabling vision mode after auto-population complete")

        except Exception as e:
            # Make sure to reset vision mode in case of error
            self._vision_mode = False
            logger.warning("Disabling vision mode due to error")

            logger.error(f"Error applying vision preprocessing results: {str(e)}")
            logger.error(f"Error traceback: {traceback.format_exc()}")

    def _update_process_button(self) -> None:
        """Update the state of the process button."""
        enabled = self.current_pdf is not None and all(
            frame["fuzzy"].get() for frame in self.filter_frames
        )
        self.process_button.setEnabled(enabled)

    def _update_display(self) -> None:
        """Update the queue display."""
        self.queue_display.update_display(self.processing_thread.tasks)

    def _clear_completed(self) -> None:
        """Clear completed tasks from the queue."""
        self.processing_thread.tasks = {
            k: v
            for k, v in self.processing_thread.tasks.items()
            if v.status != "completed"
        }
        # Immediately update the UI to reflect the changes
        self._update_display()

    def _retry_failed(self) -> None:
        """Retry failed tasks."""
        for task in self.processing_thread.tasks.values():
            if task.status == "failed":
                task.status = "pending"
                task.error_msg = ""
        # Immediately update the UI to reflect the changes
        self._update_display()

    def _on_task_completed(self, task_id: str, status: str) -> None:
        """Handle task completion for PDF processing tasks.

        Note: This does NOT handle vision preprocessing, which is handled separately
        through the vision result signal system.
        """
        logger = get_logger()
        if task_id in self.processing_thread.tasks:
            task = self.processing_thread.tasks[task_id]
            task.status = status
            task.end_time = datetime.now()

            # Immediately update the UI to reflect the status change
            self._update_display()

            # If task is completed successfully, mark as processed but don't reload current PDF
            if status == "completed":
                logger.info(f"PDF processing task completed successfully: {task_id}")

                # Mark the source file as processed in our tracking system
                # This ensures we won't pick it up again even if it's not deleted
                if task.pdf_path:
                    # Also track the original location if different
                    paths_to_mark = {task.pdf_path}

                    if task.original_pdf_location and not self.pdf_manager._paths_equal(
                        task.original_pdf_location, task.pdf_path
                    ):
                        paths_to_mark.add(task.original_pdf_location)

                    # Mark all unique paths as processed
                    for path in paths_to_mark:
                        self.pdf_manager.mark_file_processed(path)
                        logger.debug(f"Marked as processed: {os.path.basename(path)}")

                # Process events to ensure any pending database writes or file operations complete
                QApplication.processEvents()

                # Only load next PDF if the current one is gone or was the one that just finished
                if (not self.current_pdf) or (
                    self.current_pdf
                    and task.pdf_path
                    and self.pdf_manager._paths_equal(self.current_pdf, task.pdf_path)
                ):
                    logger.debug(
                        f"Loading next PDF after task completion (current PDF is {self.current_pdf})"
                    )
                    # Use a timer to load the next PDF after a brief delay
                    QTimer.singleShot(1000, self._load_next_pdf)
                else:
                    logger.debug(
                        f"Keeping current PDF displayed: {os.path.basename(self.current_pdf)}"
                    )

                    # Just update the process button state without reloading
                    self._update_process_button()

    def _on_task_failed(self, task_id: str, error_msg: str) -> None:
        """Handle task failure."""
        logger = get_logger()
        if task_id in self.processing_thread.tasks:
            task = self.processing_thread.tasks[task_id]
            task.status = "failed"
            task.error_msg = error_msg
            task.end_time = datetime.now()
            logger.error(f"PDF processing task {task_id} failed: {error_msg}")

            # Immediately update the UI to reflect the status change
            self._update_display()

            # Update status
            self._update_status(f"Task failed: {error_msg}")

            # Load next PDF if this was the current one
            if (
                self.current_pdf
                and task.pdf_path
                and self.pdf_manager._paths_equal(self.current_pdf, task.pdf_path)
            ):
                QTimer.singleShot(1000, self._load_next_pdf)

    def _on_task_started(self, task_id: str) -> None:
        """Handle task start."""
        logger = get_logger()
        logger.info(f"PDF processing task started: {task_id}")

        # Immediately update the UI to reflect the status change
        self._update_display()

    def _on_config_change(self) -> None:
        """Handle configuration changes."""
        logger = get_logger()

        # If we're already applying a config change, don't schedule another one
        if self._is_applying_config:
            logger.debug(
                "Config change requested while already applying changes - ignoring"
            )
            return

        # Cancel any pending operation
        if self._pending_config_change_id is not None:
            self._update_timer.stop()
            self._pending_config_change_id = None

        # Schedule the change with a delay to debounce multiple rapid changes
        logger.debug("Scheduling config change with 250ms debounce delay")
        self._pending_config_change_id = self._update_timer.singleShot(
            250,  # 250ms delay
            self._apply_config_change,
        )

    def _apply_config_change(self) -> None:
        """Apply configuration changes."""
        logger = get_logger()

        # Reset pending change ID
        self._pending_config_change_id = None

        # Set flag to prevent concurrent config changes
        self._is_applying_config = True
        logger.info("Applying configuration changes...")

        try:
            # Store old config values for comparison
            old_excel_file = self.excel_manager._last_file
            old_excel_sheet = self.excel_manager._last_sheet

            # Get new config
            config = self.config_manager.get_config()
            new_excel_file = config.get("excel_file")
            new_excel_sheet = config.get("excel_sheet")

            # Update vision button enabled state
            vision_enabled = config.get("vision", {}).get("enabled", False)
            self.vision_button.setEnabled(vision_enabled)
            if not vision_enabled:
                self.vision_button.setToolTip(
                    "Vision processing is disabled in configuration"
                )
                logger.debug("Vision processing disabled in configuration")
            else:
                self.vision_button.setToolTip(
                    "Manually run vision processing on current PDF"
                )
                logger.debug("Vision processing enabled in configuration")

            # Check if Excel file or sheet changed
            excel_changed = (
                new_excel_file != old_excel_file or new_excel_sheet != old_excel_sheet
            )

            # Reload Excel data and refresh hyperlink cache if changed
            if excel_changed and new_excel_file and new_excel_sheet:
                logger.info(
                    f"Excel configuration changed, reloading data and cache: {new_excel_file}, sheet: {new_excel_sheet}"
                )
                self._update_status("Reloading Excel data and cache...")
                try:
                    # Force reload of data
                    self.excel_manager.load_excel_data(
                        new_excel_file, new_excel_sheet, force_reload=True
                    )
                    # Refresh hyperlink cache (this might take time)
                    # Consider running this in a thread if it blocks UI
                    self.excel_manager.refresh_hyperlink_cache(
                        new_excel_file, new_excel_sheet
                    )
                    self._update_status("Excel data and cache reloaded.")
                    logger.info("Excel data and hyperlink cache successfully reloaded")
                except Exception as e:
                    logger.error(f"Error reloading Excel data: {str(e)}")
                    self._handle_error(e, "reloading Excel data after config change")
                    self._update_status("Error reloading Excel data.")
            elif excel_changed:
                # Excel config removed or incomplete, clear data
                logger.warning(
                    "Excel configuration removed or incomplete, clearing data"
                )
                self.excel_manager.clear_caches()

            # Always rebuild filters and try loading next PDF
            self._setup_filters()
            self._load_next_pdf()

        except Exception as e:
            # Handle any errors during config change
            self._handle_error(e, "applying configuration changes")
            logger.error(f"Error during config change: {str(e)}")
        finally:
            # Always reset the flag when done, even if an error occurred
            self._is_applying_config = False
            logger.info("Configuration change completed")

    def closeEvent(self, event: Any) -> None:
        """Handle tab closure."""
        logger = get_logger()
        logger.info("Processing tab closing, stopping processing thread")
        self.processing_thread.stop()
        super().closeEvent(event)

    def _show_warning(self, message: str) -> None:
        """Show a non-blocking warning to the user."""
        # Log the warning
        logger = get_logger()
        logger.warning(f"UI Warning: {message}")

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
        """Handle errors in a way appropriate to their severity."""
        # Get logger
        logger = get_logger()

        # Log the error
        error_msg = f"Error {context}: {str(error)}"
        logger.error(error_msg)

        # Log traceback for debugging
        if hasattr(error, "__traceback__"):
            logger.error(
                f"Traceback: {traceback.format_exception(type(error), error, error.__traceback__)}"
            )

        # Determine if this is a critical error that should show a blocking dialog
        is_critical = True

        # Non-critical errors:
        # 1. Excel file access errors
        if isinstance(error, OSError) and "excel" in context.lower():
            is_critical = False
            logger.warning(f"Non-critical Excel access error: {error_msg}")
            self._show_warning(f"Error {context}:\n{str(error)}")

        # 2. PDF loading errors
        elif "pdf" in context.lower() and "load" in context.lower():
            is_critical = False
            logger.warning(f"Non-critical PDF loading error: {error_msg}")
            self._show_warning(f"Error {context}:\n{str(error)}")

        # 3. Excel data loading errors
        elif "excel" in context.lower() and "load" in context.lower():
            is_critical = False
            logger.warning(f"Non-critical Excel data loading error: {error_msg}")
            self._show_warning(f"Error {context}:\n{str(error)}")

        # For critical errors, use the error handler
        if is_critical:
            logger.error(
                f"Critical error - delegating to main error handler: {error_msg}"
            )
            self._error_handler(error, context)

        # Always update the status bar
        self._update_status(f"Error: {context}")

    def _get_available_filter_values(self, filter_index):
        """Get all available values for a specific filter."""
        logger = get_logger()
        try:
            # Make sure filter frames exist
            if not self.filter_frames or filter_index >= len(self.filter_frames):
                logger.debug(f"No filter frames available for index {filter_index}")
                return []

            # Get values from the filter's fuzzy search
            fuzzy = self.filter_frames[filter_index]["fuzzy"]
            values = fuzzy.all_values

            logger.debug(
                f"Got {len(values)} available values for filter {filter_index + 1}"
            )
            return values
        except Exception as e:
            logger.error(f"Error getting available filter values: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(
                    f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}"
                )
            return []

    def _manual_vision_processing(self) -> None:
        """Manually trigger vision preprocessing to populate filters for the current PDF."""
        logger = get_logger()

        if not self.current_pdf:
            logger.info("Manual vision processing attempted with no file loaded")
            self._update_status("No file loaded")
            return

        try:
            logger.info(f"Starting manual vision preprocessing for {self.current_pdf}")
            self._update_status("Running vision preprocessing...")

            # Clear filter values but don't clear the filter_frames list itself
            for frame in self.filter_frames:
                frame["fuzzy"].clear()

            # Start vision processing and wait for results
            self._start_vision_processing(self.current_pdf)

            self._update_status("Vision preprocessing started")
            logger.info("Vision preprocessing started successfully")
        except Exception as e:
            logger.error(f"Error in manual vision preprocessing: {str(e)}")
            self._handle_error(e, "manual vision preprocessing")
