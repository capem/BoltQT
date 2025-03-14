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
from PyQt6.QtCore import Qt, QTimer

from src.ui.config_tab import ConfigTab
from src.ui.processing_tab import ProcessingTab
from src.ui.loading_screen import EnhancedLoadingScreen
from src.utils.config_manager import ConfigManager
from src.utils.excel_manager import ExcelManager
from src.utils.pdf_manager import PDFManager

class MainWindow(QMainWindow):
    """Main window of the application."""
    
    def __init__(self, loading_screen: EnhancedLoadingScreen) -> None:
        super().__init__()
        
        # Store loading screen reference
        self.loading_screen = loading_screen
        
        # Initialize managers
        self.loading_screen.set_progress(10, "Initializing managers...")
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
        self.loading_screen.set_progress(30, "Creating tabs...")
        self.config_tab = ConfigTab(
            self.config_manager,
            self.excel_manager,
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
        
        # Hide loading screen after a short delay
        self.loading_screen.set_progress(100, "Ready!")
        QTimer.singleShot(500, self.loading_screen.hide)

def main() -> None:
    """Main entry point of the application."""
    app = QApplication(sys.argv)
    
    # Set application-wide style
    app.setStyle("Fusion")
    
    # Create and show loading screen first
    loading_screen = EnhancedLoadingScreen(app_name="File Organizer")
    loading_screen.show()
    
    # Center the loading screen
    screen = app.primaryScreen().availableGeometry()
    loading_screen.move(
        (screen.width() - loading_screen.width()) // 2,
        (screen.height() - loading_screen.height()) // 2
    )
    
    # Process any pending events to ensure the loading screen is shown
    app.processEvents()
    
    # Create and show main window
    window = MainWindow(loading_screen)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()