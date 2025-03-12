#!/usr/bin/env python3
from __future__ import annotations

import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QWidget,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

from src.ui.config_tab import ConfigTab
from src.ui.processing_tab import ProcessingTab
from src.utils.config_manager import ConfigManager
from src.utils.excel_manager import ExcelManager
from src.utils.pdf_manager import PDFManager

class MainWindow(QMainWindow):
    """Main window of the application."""
    
    def __init__(self) -> None:
        super().__init__()
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.excel_manager = ExcelManager()
        self.pdf_manager = PDFManager()
        
        # Set window properties
        self.setWindowTitle("File Organizer")
        self.setMinimumSize(1200, 800)
        
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Create layout for central widget
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Error and status handlers
        def handle_error(error: Exception, context: str) -> None:
            from src.ui.error_dialog import show_error
            show_error(self, context, error)
            
        def handle_status(message: str) -> None:
            self.status_bar.showMessage(message)
        
        # Create tabs
        self.config_tab = ConfigTab(
            self.config_manager,
            handle_error,
            handle_status
        )
        
        self.processing_tab = ProcessingTab(
            self.config_manager,
            self.excel_manager,
            self.pdf_manager,
            handle_error,
            handle_status
        )
        
        # Add tabs
        self.tab_widget.addTab(self.config_tab, "Configuration")
        self.tab_widget.addTab(self.processing_tab, "Processing")

def main() -> None:
    """Main entry point of the application."""
    app = QApplication(sys.argv)
    
    # Set application-wide style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()