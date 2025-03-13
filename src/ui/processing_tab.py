from __future__ import annotations
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import time

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSplitter,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from ..utils import ConfigManager, ExcelManager, PDFManager, PDFTask
from .fuzzy_search import FuzzySearchFrame
from .queue_display import QueueDisplay
from .pdf_viewer import PDFViewer
from .error_dialog import ErrorDialog

class ProcessingThread(QThread):
    """Background thread for processing PDFs."""
    
    task_completed = pyqtSignal(str, str)  # task_id, status
    task_failed = pyqtSignal(str, str)     # task_id, error_message
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.tasks: Dict[str, PDFTask] = {}
        self.running = True
    
    def run(self) -> None:
        """Process tasks in the queue."""
        while self.running:
            # Find next pending task
            task_to_process = None
            task_id = None
            
            for id, task in self.tasks.items():
                if task.status == "pending":
                    task_to_process = task
                    task_id = id
                    task.status = "processing"
                    break
            
            if not task_to_process:
                time.sleep(0.1)
                continue
            
            try:
                # Process task here
                # This will be implemented when we add the task processing logic
                pass
                
            except Exception as e:
                self.task_failed.emit(task_id, str(e))
            else:
                self.task_completed.emit(task_id, "completed")
    
    def stop(self) -> None:
        """Stop the processing thread."""
        self.running = False
        self.wait()

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
        
        # Initialize processing thread before UI setup
        self.processing_thread = ProcessingThread(self)
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
        
        # Right panel (Queue)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
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
                on_tab=lambda e, idx=i-1: self._handle_filter_tab(e, idx)
            )
            # Connect value_selected signal to update dependent filters
            fuzzy.value_selected.connect(lambda idx=i-1: self._on_filter_selected(idx))
            layout.addWidget(fuzzy)
            
            # Add to main layout
            self.filters_layout.addWidget(frame)
            
            # Store filter info
            self.filter_frames.append({
                "frame": frame,
                "label": label,
                "fuzzy": fuzzy,
                "column": column
            })
            
            i += 1
        
        # Add stretch at the end
        self.filters_layout.addStretch()
        
        # Load initial values for first filter
        if self.filter_frames:
            self._load_filter_values(0)
    
    def _load_filter_values(self, filter_index: int = 0) -> None:
        """Load values for a specific filter.
        
        Args:
            filter_index: Index of the filter to load values for (0-based)
        """
        try:
            config = self.config_manager.get_config()
            if not (config["excel_file"] and config["excel_sheet"]):
                return
                
            # Load Excel data if needed
            if self.excel_manager.excel_data is None:
                self.excel_manager.load_excel_data(
                    config["excel_file"],
                    config["excel_sheet"]
                )
            
            # If we have no filters, exit
            if not self.filter_frames or filter_index >= len(self.filter_frames):
                return
                
            # Get the dataframe
            df = self.excel_manager.excel_data
            
            # Apply filters for all previous filters
            filtered_df = df.copy()
            for i in range(filter_index):
                # Skip if we don't have a value for this filter
                selected_value = self.filter_frames[i]["fuzzy"].get()
                if not selected_value:
                    continue
                    
                # Apply filter
                column = self.filter_frames[i]["column"]
                filtered_df = filtered_df[filtered_df[column].astype(str) == selected_value]
            
            # Get values for the current filter
            column = self.filter_frames[filter_index]["column"]
            values = sorted(filtered_df[column].astype(str).unique().tolist())
            values = [str(x).strip() for x in values]
            self.filter_frames[filter_index]["fuzzy"].set_values(values)
                
        except Exception as e:
            self._handle_error(e, f"loading filter values for filter {filter_index+1}")
    
    def _on_filter_selected(self, filter_index: int) -> None:
        """Handle selection in a filter.
        
        Args:
            filter_index: Index of the filter where selection occurred (0-based)
        """
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
            # The button will be highlighted by the focus style in Qt
        return "break"
    
    def _process_current_file(self) -> None:
        """Process the current file."""
        if not self.current_pdf:
            self._update_status("No file selected")
            return
            
        # Get filter values
        filter_values = []
        for frame in self.filter_frames:
            value = frame["fuzzy"].get()
            if not value:
                self._update_status("All filters must be set")
                return
            filter_values.append(value)
        
        # Create task
        task = PDFTask(
            pdf_path=self.current_pdf,
            filter_values=filter_values,
            start_time=datetime.now()
        )
        
        # Add to processing queue
        self.processing_thread.tasks[task.task_id] = task
        
        # Load next file
        self._load_next_pdf()
    
    def _load_next_pdf(self, skip: bool = False) -> None:
        """Load the next PDF file."""
        try:
            if skip and self.current_pdf:
                # Create skipped task
                task = PDFTask(
                    pdf_path=self.current_pdf,
                    status="skipped",
                    start_time=self.current_pdf_start_time or datetime.now(),
                    end_time=datetime.now()
                )
                self.processing_thread.tasks[task.task_id] = task
            
            # Get next file
            config = self.config_manager.get_config()
            if not config["source_folder"]:
                self._update_status("Source folder not configured")
                return
                
            active_tasks = {
                k: v for k, v in self.processing_thread.tasks.items()
                if v.status in ["pending", "processing"]
            }
            
            next_pdf = self.pdf_manager.get_next_pdf(
                config["source_folder"],
                active_tasks
            )
            
            if next_pdf:
                self.current_pdf = next_pdf
                self.current_pdf_start_time = datetime.now()
                self.pdf_viewer.display_pdf(next_pdf)
                
                # Clear filters
                for frame in self.filter_frames:
                    frame["fuzzy"].clear()
                
                # Load first filter values
                self._load_filter_values()
                
                self._update_status("Ready")
            else:
                self.current_pdf = None
                self.current_pdf_start_time = None
                self.pdf_viewer.display_pdf(None)
                self._update_status("No files to process")
            
            # Update process button state
            self._update_process_button()
            
        except Exception as e:
            self._handle_error(e, "loading next PDF")
    
    def _update_process_button(self) -> None:
        """Update the state of the process button."""
        enabled = (
            self.current_pdf is not None
            and all(frame["fuzzy"].get() for frame in self.filter_frames)
        )
        self.process_button.setEnabled(enabled)
    
    def _update_display(self) -> None:
        """Update the queue display."""
        self.queue_display.update_display(self.processing_thread.tasks)
    
    def _clear_completed(self) -> None:
        """Clear completed tasks from the queue."""
        self.processing_thread.tasks = {
            k: v for k, v in self.processing_thread.tasks.items()
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
            self._apply_config_change
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