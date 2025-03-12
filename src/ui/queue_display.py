from __future__ import annotations
from typing import Dict, List, Any, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableView,
    QPushButton,
    QHBoxLayout,
    QHeaderView,
    QMenu,
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QColor, QAction
from datetime import datetime
from ..utils.models import PDFTask

class QueueTableModel(QAbstractTableModel):
    """Model for displaying queue data in a table view."""
    
    HEADERS = ["File", "Status", "Start Time", "End Time", "Duration", "Error"]
    STATUS_COLORS = {
        "pending": QColor("#fff3cd"),     # Light yellow
        "processing": QColor("#cfe2ff"),   # Light blue
        "completed": QColor("#d1e7dd"),    # Light green
        "failed": QColor("#f8d7da"),      # Light red
        "reverted": QColor("#e2e3e5"),    # Light gray
        "skipped": QColor("#e2e3e5"),     # Light gray
    }
    
    def __init__(self) -> None:
        super().__init__()
        self._tasks: List[PDFTask] = []
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._tasks)
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.HEADERS)
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
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
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Create table
        self.table = QTableView()
        self.model = QueueTableModel()
        self.table.setModel(self.model)
        
        # Configure table appearance
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        
        # Configure column sizes
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # File
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)    # Status
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # Start Time
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)    # End Time
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)    # Duration
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Error
        
        header.setMinimumSectionSize(80)
        self.table.setColumnWidth(1, 100)  # Status
        self.table.setColumnWidth(2, 100)  # Start Time
        self.table.setColumnWidth(3, 100)  # End Time
        self.table.setColumnWidth(4, 80)   # Duration
        
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
        self.table.customContextMenuRequested.connect(self._show_context_menu)
    
    def update_display(self, tasks: Dict[str, PDFTask]) -> None:
        """Update the display with new task data."""
        self.model.update_tasks(tasks)
    
    def _show_context_menu(self, pos) -> None:
        """Show context menu for selected task."""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        
        task = self.model._tasks[index.row()]
        if task.status != "failed" or not task.error_msg:
            return
        
        menu = QMenu(self)
        action = QAction("Show Error Details", self)
        action.triggered.connect(lambda: self._show_error_details(task))
        menu.addAction(action)
        
        menu.exec(self.table.viewport().mapToGlobal(pos))
    
    def _show_error_details(self, task: PDFTask) -> None:
        """Show error details for a failed task."""
        from .error_dialog import ErrorDialog
        ErrorDialog(
            self,
            "Processing Error",
            f"Error processing {task.pdf_path}:\n{task.error_msg}"
        )