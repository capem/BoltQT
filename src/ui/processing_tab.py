from __future__ import annotations
from typing import Optional, Any, Callable
from datetime import datetime
import time
import os

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSplitter,
    QApplication,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer

from ..utils import ConfigManager, ExcelManager, PDFManager, PDFTask
from ..utils.processing_thread import ProcessingThread
from .fuzzy_search import FuzzySearchFrame
from .queue_display import QueueDisplay
from .pdf_viewer import PDFViewer


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
        error_handler: Callable[[Exception, str], None],
        status_handler: Callable[[str], None],
    ) -> None:
        super().__init__()
        ProcessingTab._instance = self

        # Store managers and handlers
        self.config_manager = config_manager
        self.excel_manager = excel_manager
        self.pdf_manager = pdf_manager
        self._handle_error = error_handler
        self._update_status = status_handler

        # Initialize state
        self._pending_config_change_id = None
        self._is_reloading = False
        self.current_pdf: Optional[str] = None
        self.current_pdf_start_time: Optional[datetime] = None
        self.filter_frames = []

        # Initialize processing thread with managers
        self.processing_thread = ProcessingThread(
            config_manager=self.config_manager,
            excel_manager=self.excel_manager,
            pdf_manager=self.pdf_manager,
        )
        self.processing_thread.task_completed.connect(self._on_task_completed)
        self.processing_thread.task_failed.connect(self._on_task_failed)
        self.processing_thread.start()

        # Create UI
        self._setup_ui()

        # Register for config changes
        self.config_manager.config_changed.connect(self._on_config_change)

    def _create_section_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a styled frame for a section."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)

        if title:
            label = QLabel(title)
            label.setStyleSheet("font-weight: bold; font-size: 12pt;")
            layout.addWidget(label)

        return frame, layout

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Create splitter for main panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left panel (Filters and Actions)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Filters section
        filters_frame, filters_layout = self._create_section_frame("Filters")

        self.filters_container = QWidget()
        self.filters_layout = QVBoxLayout(self.filters_container)
        filters_layout.addWidget(self.filters_container)

        left_layout.addWidget(filters_frame)

        # Actions section
        actions_frame, actions_layout = self._create_section_frame("Actions")

        # Process button
        self.process_button = QPushButton("Process File")
        self.process_button.clicked.connect(self._process_current_file)
        self.process_button.setEnabled(False)
        # Make the process button the default button so it responds to Enter key press
        self.process_button.setDefault(True)
        self.process_button.setAutoDefault(True)
        # Add focus style
        self.process_button.setStyleSheet("""
            QPushButton:focus {
                background-color: #cce4ff;
                border: 2px solid #007bff;
            }
        """)
        actions_layout.addWidget(self.process_button)

        # Skip button
        self.skip_button = QPushButton("Skip File")
        self.skip_button.clicked.connect(lambda: self._load_next_pdf(skip=True))
        actions_layout.addWidget(self.skip_button)

        left_layout.addWidget(actions_frame)
        left_layout.addStretch()

        # Center panel (PDF Viewer)
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # PDF viewer section
        viewer_frame, viewer_layout = self._create_section_frame("PDF Viewer")

        # PDF viewer
        self.pdf_viewer = PDFViewer(self.pdf_manager)
        viewer_layout.addWidget(self.pdf_viewer)

        center_layout.addWidget(viewer_frame)

        # Right panel (File Info and Queue)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # File Information section
        info_frame, info_layout = self._create_section_frame("File Information")

        # Create clickable label for file information
        self.file_info_label = QLabel("No file loaded")
        self.file_info_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QLabel:hover {
                background-color: #e9ecef;
                border-color: #ced4da;
            }
        """)
        self.file_info_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_info_label.mousePressEvent = lambda e: self._select_pdf_file()
        info_layout.addWidget(self.file_info_label)

        right_layout.addWidget(info_frame)

        # Queue section
        queue_frame, queue_layout = self._create_section_frame("Processing Queue")

        # Queue display
        self.queue_display = QueueDisplay()
        self.queue_display.clear_button.clicked.connect(self._clear_completed)
        self.queue_display.retry_button.clicked.connect(self._retry_failed)
        queue_layout.addWidget(self.queue_display)

        right_layout.addWidget(queue_frame)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)

        # Set initial sizes (proportional)
        splitter.setSizes([200, 600, 200])

        # Load initial data
        self._setup_filters()
        self._load_next_pdf()

        # Start periodic updates
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.start(500)  # Update every 500ms

    def _setup_filters(self) -> None:
        """Setup filter controls based on configuration."""
        config = self.config_manager.get_config()

        # Clear existing filters
        for frame in self.filter_frames:
            frame["frame"].deleteLater()
        self.filter_frames.clear()

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
            label.setStyleSheet("font-weight: bold;")
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
            layout.addWidget(fuzzy)

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
        self, value: str, row_idx: int, has_hyperlink: bool = False
    ) -> str:
        """Format filter2 value with row number and checkmark if hyperlinked."""
        import re

        # Check if value already contains Excel Row information
        if re.search(r"⟨Excel Row[:-]\s*\d+⟩", value):
            # Already has Excel Row info, just add checkmark if needed
            if has_hyperlink and not value.startswith("✓ "):
                return "✓ " + value
            return value

        prefix = "✓ " if has_hyperlink else ""
        # +2 because Excel is 1-based and has header
        return f"{prefix}{value} ⟨Excel Row: {row_idx + 2}⟩"

    def _parse_filter2_value(self, formatted_value: str) -> tuple[str, int]:
        """Parse filter2 value to get original value and row number."""
        import re

        if not formatted_value:
            print("[DEBUG] UI received empty filter2 value")
            return "", -1

        # Remove checkmark if present
        formatted_value = formatted_value.replace("✓ ", "", 1)
        match = re.match(r"(.*?)\s*⟨Excel Row:\s*(\d+)⟩", formatted_value)
        if match:
            value = match.group(1).strip()
            row_num = int(match.group(2))
            print(
                f"[DEBUG] UI parsed filter2 value: '{formatted_value}' -> value='{value}', row={row_num - 2}"
            )
            return value, row_num - 2  # Convert back to 0-based index

        print(f"[DEBUG] UI failed to parse filter2 value: '{formatted_value}'")
        return formatted_value, -1

    def _load_filter_values(self, filter_index: int = 0) -> None:
        """Load values for a specific filter."""
        try:
            config = self.config_manager.get_config()
            if not (config["excel_file"] and config["excel_sheet"]):
                return

            # Load Excel data if needed
            if self.excel_manager.excel_data is None:
                self.excel_manager.load_excel_data(
                    config["excel_file"], config["excel_sheet"]
                )

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
                    clean_value, parsed_row_idx = self._parse_filter2_value(selected_value)
                    selected_value = clean_value
                    row_idx = parsed_row_idx
                    print(f"[DEBUG] Parsed filter2: value='{clean_value}', row_idx={row_idx}")
                # For filter3 and beyond, check row_idx
                if i > 1:
                    # Clear and return if no valid row_idx from filter2
                    if row_idx < 0 or row_idx not in filtered_df.index:
                        print(f"[DEBUG] No valid row_idx for filter {i+1}, clearing all subsequent filters")
                        for idx in range(i, len(self.filter_frames)):
                            self.filter_frames[idx]["fuzzy"].clear()
                        return
                    else:
                        filtered_df = filtered_df.loc[[row_idx]]
                        print(f"[DEBUG] Applied row_idx filter: {row_idx}")
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
                # Cache hyperlinks for the filter2 column
                self.excel_manager.cache_hyperlinks_for_column(
                    config["excel_file"], config["excel_sheet"], column
                )

                # Get all rows from filtered_df, not just unique values
                formatted_values = []

                # Process each row individually
                for idx, row in filtered_df.iterrows():
                    value = str(row[column]).strip()
                    has_hyperlink = self.excel_manager.has_hyperlink(idx)
                    formatted_value = self._format_filter2_value(
                        value, idx, has_hyperlink
                    )
                    formatted_values.append(formatted_value)

                # Sort the formatted values for better user experience
                formatted_values.sort()
                values = formatted_values
            else:
                # For filter3 and beyond, must have valid row_idx from filter2
                if filter_index > 1:
                    filter2_value = self.filter_frames[1]["fuzzy"].get()
                    if not filter2_value:
                        print("[DEBUG] No filter2 value selected, keeping subsequent filters empty")
                        return
                    
                    _, row_idx = self._parse_filter2_value(filter2_value)
                    if row_idx < 0 or row_idx not in filtered_df.index:
                        print(f"[DEBUG] No valid row_idx from filter2, keeping filter {filter_index + 1} empty")
                        return
                    
                    # Use only the specific row for valid row_idx
                    filtered_df = filtered_df.loc[[row_idx]]
                    print(f"[DEBUG] Using row_idx {row_idx} for filter {filter_index + 1}")

                # Get unique values from filtered data
                values = sorted(filtered_df[column].astype(str).unique().tolist())

            # Update the fuzzy search values
            values = [str(x).strip() for x in values]
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

    def _handle_filter_tab(self, event: Any, filter_index: int) -> str:
        """Handle tab key in filter."""
        if filter_index < len(self.filter_frames) - 1:
            # Move to next filter
            self.filter_frames[filter_index + 1]["fuzzy"].entry.setFocus()
        else:
            # Move to process button and visually highlight it
            self.process_button.setFocus()
        return "break"

    def _process_current_file(self) -> None:
        """Process the current file."""
        if not self.current_pdf:
            self._update_status("No file selected")
            return

        # Get filter values
        filter_values = []
        formatted_filter_values = []  # Store the original formatted values

        for i, frame in enumerate(self.filter_frames):
            value = frame["fuzzy"].get()
            if not value:
                self._update_status("All filters must be set")
                return

            # Store the original formatted value
            formatted_filter_values.append(value)

            # For filter2, extract the clean value without formatting
            if i == 1:
                clean_value, row_idx = self._parse_filter2_value(value)
                print(
                    f"[DEBUG] Processing filter2 value: '{value}' -> clean='{clean_value}', row={row_idx}"
                )
                value = clean_value

            filter_values.append(value)

        # Store the current PDF path before closing it
        current_pdf_path = self.current_pdf

        # Clear the PDF from the viewer to release file handles
        self.pdf_viewer.clear_pdf()

        # Create task
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
                print(
                    f"[DEBUG] Pre-setting task row_idx to {row_idx} from filter2 value"
                )

        # Add to processing queue
        self.processing_thread.tasks[task.task_id] = task

        print(
            f"[DEBUG] Added task {task.task_id} to queue with filter values: {filter_values}"
        )

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
            self.file_info_label.setText(f"File: {os.path.basename(file_path)}")
        else:
            self.file_info_label.setText("No file loaded")

    def _load_next_pdf(self, skip: bool = False) -> None:
        """Load the next PDF file with improved file handle management."""
        try:
            print(
                f"[DEBUG] _load_next_pdf called with skip={skip}, current_pdf={self.current_pdf}"
            )

            # Handle skipped files first
            if skip and self.current_pdf:
                # Create skipped task
                task = PDFTask(
                    pdf_path=self.current_pdf,
                    status="skipped",
                    start_time=self.current_pdf_start_time or datetime.now(),
                    end_time=datetime.now(),
                )
                self.processing_thread.tasks[task.task_id] = task
                self.pdf_manager.mark_file_processed(self.current_pdf)

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
                                print(
                                    f"[DEBUG] Retry {attempt + 1}: Error clearing PDF: {str(e)}"
                                )
                                time.sleep(0.5)  # Short delay between retries
                                continue
                            raise

                    # Reset state variables and update UI
                    self.current_pdf = None
                    self.current_pdf_start_time = None
                    self._update_file_info_label()

                except Exception as cleanup_error:
                    print(
                        f"[DEBUG] Warning: Error during PDF cleanup: {str(cleanup_error)}"
                    )
                    # Continue even if cleanup fails

            # Get config and validate
            config = self.config_manager.get_config()
            if not config["source_folder"]:
                self._update_status("Source folder not configured")
                return

            # Get active tasks
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
                        print(
                            f"[DEBUG] Retry {attempt + 1}: Error getting next PDF: {str(e)}"
                        )
                        time.sleep(0.5)
                        continue
                    raise

            if next_pdf:
                print(f"[DEBUG] Loading next PDF: {next_pdf}")
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

                # Focus first filter
                if self.filter_frames:
                    self.filter_frames[0]["fuzzy"].entry.setFocus()

                self._update_status("Ready")
            else:
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

    def _retry_failed(self) -> None:
        """Retry failed tasks."""
        for task in self.processing_thread.tasks.values():
            if task.status == "failed":
                task.status = "pending"
                task.error_msg = ""

    def _on_task_completed(self, task_id: str, status: str) -> None:
        """Handle task completion."""
        if task_id in self.processing_thread.tasks:
            task = self.processing_thread.tasks[task_id]
            task.status = status
            task.end_time = datetime.now()

            # If task is completed successfully, mark as processed but don't reload current PDF
            if status == "completed":
                print(f"[DEBUG] Task completed successfully: {task_id}")

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
                        print(f"[DEBUG] Marked as processed: {os.path.basename(path)}")

                # Process events to ensure any pending database writes or file operations complete
                QApplication.processEvents()

                # Only load next PDF if the current one is gone or was the one that just finished
                if (not self.current_pdf) or (
                    self.current_pdf
                    and task.pdf_path
                    and self.pdf_manager._paths_equal(self.current_pdf, task.pdf_path)
                ):
                    print(
                        f"[DEBUG] Loading next PDF after task completion (current PDF is {self.current_pdf})"
                    )
                    # Use a timer to load the next PDF after a brief delay
                    QTimer.singleShot(1000, self._load_next_pdf)
                else:
                    print(
                        f"[DEBUG] Keeping current PDF displayed: {os.path.basename(self.current_pdf)}"
                    )

                    # Just update the process button state without reloading
                    self._update_process_button()

    def _on_task_failed(self, task_id: str, error_msg: str) -> None:
        """Handle task failure."""
        if task_id in self.processing_thread.tasks:
            task = self.processing_thread.tasks[task_id]
            task.status = "failed"
            task.error_msg = error_msg
            task.end_time = datetime.now()

    def _on_config_change(self) -> None:
        """Handle configuration changes."""
        # Cancel any pending operation
        if self._pending_config_change_id is not None:
            self._update_timer.stop()
            self._pending_config_change_id = None

        # Schedule the change
        self._pending_config_change_id = self._update_timer.singleShot(
            250,  # 250ms delay
            self._apply_config_change,
        )

    def _apply_config_change(self) -> None:
        """Apply configuration changes."""
        self._pending_config_change_id = None
        self._setup_filters()
        self._load_next_pdf()

    def closeEvent(self, event: Any) -> None:
        """Handle tab closure."""
        self.processing_thread.stop()
        super().closeEvent(event)
