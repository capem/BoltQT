from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QEvent
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..utils.models import PDFTask


class QueueTableModel(QAbstractTableModel):
    """Model for displaying queue data in a table view."""

    HEADERS = ["File", "Status", "Start Time", "End Time", "Duration", "Error"]
    STATUS_COLORS = {
        "pending": QColor("#fff3cd"),  # Light yellow
        "processing": QColor("#cfe2ff"),  # Light blue
        "completed": QColor("#d1e7dd"),  # Light green
        "failed": QColor("#f8d7da"),  # Light red
        "reverted": QColor("#e2e3e5"),  # Light gray
        "skipped": QColor("#e2e3e5"),  # Light gray
    }

    def __init__(self) -> None:
        super().__init__()
        self._tasks: List[PDFTask] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._tasks)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        task = self._tasks[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:  # File
                return task.pdf_path
            elif col == 1:  # Status
                return task.status.title()
            elif col == 2:  # Start Time
                return task.start_time.strftime("%H:%M:%S") if task.start_time else ""
            elif col == 3:  # End Time
                return task.end_time.strftime("%H:%M:%S") if task.end_time else ""
            elif col == 4:  # Duration
                duration = task.duration()
                return f"{duration:.1f}s" if duration is not None else ""
            elif col == 5:  # Error
                return task.error_msg

        elif role == Qt.ItemDataRole.BackgroundRole:
            return self.STATUS_COLORS.get(task.status, QColor("white"))

        return None

    def update_tasks(self, tasks: Dict[str, PDFTask]) -> None:
        """Update the model with new task data."""
        self.beginResetModel()
        self._tasks = list(tasks.values())
        self._tasks.sort(key=lambda x: x.start_time or datetime.max, reverse=True)
        self.endResetModel()


class QueueDisplay(QWidget):
    """Widget for displaying the processing queue."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Store tasks
        self.tasks = {}

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Status counters
        self.counters = QWidget()
        counter_layout = QHBoxLayout(self.counters)
        counter_layout.setContentsMargins(0, 5, 0, 15)

        self.total_label = QLabel("Total: 0")
        self.completed_label = QLabel("Completed: 0")
        self.failed_label = QLabel("Failed: 0")
        self.skipped_label = QLabel("Skipped: 0")

        for label in [
            self.total_label,
            self.completed_label,
            self.failed_label,
            self.skipped_label,
        ]:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            counter_layout.addWidget(label)

        layout.addWidget(self.counters)

        # Create table
        self.table = QTableView()
        self.model = QueueTableModel()
        self.table.setModel(self.model)

        # Configure table appearance
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()

        # Configure column sizes - all interactive for consistent scrolling
        header = self.table.horizontalHeader()
        
        # All columns are manually resizeable (interactive)
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        # Set consistent column sizing for smooth scrolling
        header.setMinimumSectionSize(80)
        header.setDefaultSectionSize(120)
        
        # Set optimal column widths for balance between usability and scrolling
        self.table.setColumnWidth(0, 250)  # File (paths)
        self.table.setColumnWidth(1, 90)   # Status
        self.table.setColumnWidth(2, 110)  # Start Time
        self.table.setColumnWidth(3, 110)  # End Time
        self.table.setColumnWidth(4, 80)   # Duration
        self.table.setColumnWidth(5, 200)  # Error

        # Optimize table view performance for smooth scrolling
        self.table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        
        # Set scrollbar policies
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Enable smooth scrolling performance optimizations
        self.table.setWordWrap(False)
        self.table.setAlternatingRowColors(True)
        
        # Set grid color for better visual consistency
        self.table.setShowGrid(False)

        # Add table to layout
        layout.addWidget(self.table)

        # Create button panel
        button_panel = QHBoxLayout()

        # Create buttons
        self.clear_button = QPushButton("Clear Completed")
        self.retry_button = QPushButton("Retry Failed")

        # Add buttons to panel
        button_panel.addWidget(self.clear_button)
        button_panel.addWidget(self.retry_button)
        button_panel.addStretch()

        # Add button panel to layout
        layout.addLayout(button_panel)

        # Set up context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._create_context_menu)
        
        # Install event filter for Ctrl+MouseWheel horizontal scrolling
        self.table.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle Shift+MouseWheel for horizontal scrolling."""
        if obj == self.table.viewport() and event.type() == QEvent.Type.Wheel:
            # Check if Shift key is pressed
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.KeyboardModifier.ShiftModifier:
                # Convert vertical wheel event to horizontal scroll
                wheel_event = event
                delta = wheel_event.angleDelta().y()
                
                # Get horizontal scrollbar
                h_scrollbar = self.table.horizontalScrollBar()
                if h_scrollbar:
                    # Scroll horizontally instead of vertically
                    scroll_value = h_scrollbar.value() - (delta // 120) * 20  # Adjust multiplier for sensitivity
                    h_scrollbar.setValue(scroll_value)
                
                # Accept the event to prevent default vertical scrolling
                return True
        
        return super().eventFilter(obj, event)

    def update_display(self, tasks: Dict[str, PDFTask]) -> None:
        """Update the display with new task data."""
        self.tasks = tasks
        self.model.update_tasks(tasks)

        # Update counters
        total = len(tasks)
        completed = sum(1 for t in tasks.values() if t.status == "completed")
        failed = sum(1 for t in tasks.values() if t.status == "failed")
        skipped = sum(1 for t in tasks.values() if t.status == "skipped")

        self.total_label.setText(f"Total: {total}")
        self.completed_label.setText(f"Completed: {completed}")
        self.failed_label.setText(f"Failed: {failed}")
        self.skipped_label.setText(f"Skipped: {skipped}")

    def _create_context_menu(self, position):
        """Create and show context menu."""
        index = self.table.indexAt(position)

        if not index.isValid():
            return

        # Get the task directly from the model's task list
        row = index.row()
        if row < 0 or row >= len(self.model._tasks):
            return

        # Get the task from the model
        task = self.model._tasks[row]
        # Get the task_id from the task object
        task_id = task.task_id

        if not task_id or task_id not in self.tasks:
            return

        task = self.tasks[task_id]

        # Map to global position for menu display
        global_pos = self.table.viewport().mapToGlobal(position)

        menu = QMenu(self)

        if task.status == "completed":
            # Show details option
            action_details = menu.addAction("View Details")
            action_details.triggered.connect(lambda: self._show_task_details(task_id))

            # Show revert option
            action_revert = menu.addAction("Revert Task")
            action_revert.triggered.connect(lambda: self._on_revert_task(task_id))

        elif task.status == "failed":
            # Show details option
            action_details = menu.addAction("View Error Details")
            action_details.triggered.connect(lambda: self._show_task_details(task_id))

            # Show retry option
            action_retry = menu.addAction("Retry")
            action_retry.triggered.connect(lambda: self._retry_task(task_id))

        # Check if the menu has any actions
        if not menu.actions():
            return

        # Show menu using exec method
        menu.exec(global_pos)

    def _show_task_details(self, task_id):
        """Show details for a selected task."""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Task Details")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)

        # Create layout
        layout = QVBoxLayout(dialog)

        # Create details text
        details_text = QTextEdit()
        details_text.setReadOnly(True)

        # Format task information
        status_colors = {
            "completed": "#4CAF50",  # Green
            "failed": "#F44336",  # Red
            "skipped": "#FF9800",  # Orange
            "pending": "#2196F3",  # Blue
            "processing": "#9C27B0",  # Purple
        }

        # Build HTML content
        html_content = f"""
        <h2>Task Details</h2>
        <p><b>Status:</b> <span style="color: {status_colors.get(task.status, "#000")};">{task.status.upper()}</span></p>
        <p><b>PDF Path:</b> {task.pdf_path}</p>
        """

        if task.processed_pdf_location:
            html_content += (
                f"<p><b>Processed Location:</b> {task.processed_pdf_location}</p>"
            )

        if task.row_idx is not None:
            html_content += f"<p><b>Excel Row:</b> {task.row_idx + 2}</p>"  # +2 for header and 1-based index

        if task.filter_values:
            html_content += "<p><b>Filter Values:</b></p><ul>"
            for i, value in enumerate(task.filter_values, 1):
                html_content += f"<li>Filter {i}: {value}</li>"
            html_content += "</ul>"

        if task.start_time:
            html_content += f"<p><b>Start Time:</b> {task.start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>"

        if task.end_time:
            html_content += (
                f"<p><b>End Time:</b> {task.end_time.strftime('%Y-%m-%d %H:%M:%S')}</p>"
            )

            # Calculate duration
            duration = task.end_time - task.start_time
            seconds = duration.total_seconds()
            html_content += f"<p><b>Duration:</b> {seconds:.2f} seconds</p>"

        if task.status == "failed" and task.error_msg:
            html_content += f"""
            <h3 style="color: #F44336;">Error Information</h3>
            <pre style="background-color: #f8f8f8; padding: 10px; border-left: 4px solid #F44336;">{task.error_msg}</pre>
            """

            # Add potential troubleshooting tips
            if "permission" in task.error_msg.lower():
                html_content += """
                <h4>Troubleshooting Tips:</h4>
                <ul>
                    <li>Check if you have write permissions to the destination folder</li>
                    <li>Verify that the file is not currently open in another application</li>
                    <li>Try running the application with administrator privileges</li>
                </ul>
                """
            elif "not found" in task.error_msg.lower():
                html_content += """
                <h4>Troubleshooting Tips:</h4>
                <ul>
                    <li>Verify that the source file exists and hasn't been moved</li>
                    <li>Check network connectivity if accessing files on a network share</li>
                </ul>
                """
            elif "path" in task.error_msg.lower():
                html_content += """
                <h4>Troubleshooting Tips:</h4>
                <ul>
                    <li>The path may contain invalid characters or is too long</li>
                    <li>Check if the drive or network share is accessible</li>
                </ul>
                """

        # Set HTML content
        details_text.setHtml(html_content)
        layout.addWidget(details_text)

        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog
        dialog.exec()

    def _retry_task(self, task_id):
        """Retry a failed task."""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        if task.status != "failed":
            return

        # Reset task status
        task.status = "pending"
        task.error_msg = ""
        task.start_time = datetime.now()
        task.end_time = None

        # Update display
        self._update_task_item(task_id, task)

        QMessageBox.information(self, "Task Retry", "Task has been queued for retry.")

    def _on_revert_task(self, task_id):
        """Handle the Revert Task action from the context menu."""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]

        # Find the ProcessingTab parent
        processing_tab = self._get_processing_tab()
        if not processing_tab:
            QMessageBox.critical(
                self, "Error", "Internal error: Could not find processing tab."
            )
            return

        # Confirm revert
        confirm = QMessageBox.question(
            self,
            "Confirm Revert",
            f"Are you sure you want to revert the task for '{os.path.basename(task.pdf_path)}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            # Get required configuration
            config = processing_tab.config_manager.get_config()

            excel_success = False
            pdf_success = False

            # Check if this task created a new row
            if getattr(task, 'created_new_row', False):
                # Remove the newly created row
                excel_success = processing_tab.excel_manager.remove_row(
                    file_path=config["excel_file"],
                    sheet_name=config["excel_sheet"],
                    row_idx=task.row_idx,
                )
                if excel_success:
                    # Update the cached DataFrame in processing thread
                    processing_tab.processing_thread._excel_data_cache["data"] = processing_tab.excel_manager.excel_data
            else:
                # Revert Excel hyperlink for existing row
                excel_success = processing_tab.excel_manager.revert_pdf_link(
                    excel_file=config["excel_file"],
                    sheet_name=config["excel_sheet"],
                    row_idx=task.row_idx,
                    filter2_col=config["filter2_column"],
                    original_hyperlink=task.original_excel_hyperlink,
                    original_value=task.filter_values[1]
                    if len(task.filter_values) > 1
                    else "",
                )

            # Revert PDF location
            pdf_success = processing_tab.pdf_manager.revert_pdf_location(task=task)

            if excel_success and pdf_success:
                # Remove the task from the tasks dictionary
                if task.task_id in processing_tab.processing_thread.tasks:
                    del processing_tab.processing_thread.tasks[task.task_id]

                # Update display
                self.update_display(processing_tab.processing_thread.tasks)

                action_type = "removed" if getattr(task, 'created_new_row', False) else "reverted"
                QMessageBox.information(
                    self,
                    "Revert Successful",
                    f"Task for '{os.path.basename(task.pdf_path)}' has been {action_type} successfully.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Partial Revert",
                    f"The task was only partially reverted. Excel: {excel_success}, PDF: {pdf_success}",
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Revert Failed", f"Failed to revert the task: {str(e)}"
            )

    def _get_processing_tab(self):
        """Get the parent ProcessingTab instance."""
        from .processing_tab import ProcessingTab

        return ProcessingTab.get_instance()
