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
    QMessageBox
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
    
    def __init__(self, loading_screen: EnhancedLoadingScreen, app: QApplication) -> None:
        super().__init__()
        
        # Store loading screen reference
        self.loading_screen = loading_screen
        self.app = app  # Store app reference
        
        # Initialize managers
        self.loading_screen.set_progress(25, "Initializing configuration manager...")
        self.app.processEvents()  # Process events to update UI
        self.config_manager = ConfigManager()
        
        self.loading_screen.set_progress(35, "Initializing Excel manager...")
        self.app.processEvents()  # Process events to update UI
        self.excel_manager = ExcelManager()
        
        self.loading_screen.set_progress(45, "Initializing PDF manager...")
        self.app.processEvents()  # Process events to update UI
        self.pdf_manager = PDFManager()
        
        # Set window properties
        self.loading_screen.set_progress(50, "Setting up main window...")
        self.app.processEvents()  # Process events to update UI
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
        self.loading_screen.set_progress(60, "Creating configuration tab...")
        self.app.processEvents()  # Process events to update UI
        self.config_tab = ConfigTab(
            self.config_manager,
            self.excel_manager,
            handle_error,
            handle_status
        )
        
        self.loading_screen.set_progress(75, "Creating processing tab...")
        self.app.processEvents()  # Process events to update UI
        self.processing_tab = ProcessingTab(
            self.config_manager,
            self.excel_manager,
            self.pdf_manager,
            handle_error,
            handle_status
        )
        
        # Add tabs
        self.loading_screen.set_progress(85, "Finalizing UI setup...")
        self.app.processEvents()  # Process events to update UI
        self.tab_widget.addTab(self.config_tab, "Configuration")
        self.tab_widget.addTab(self.processing_tab, "Processing")
        
        # Hide loading screen after a short delay
        self.loading_screen.set_progress(100, "Ready!")
        self.app.processEvents()  # Process events to update UI
        QTimer.singleShot(500, self.loading_screen.hide)

def main() -> int:
    # Create application first
    app = QApplication(sys.argv)
    
    # Set application-wide style
    app.setStyle("Fusion")
    
    # Application name - define once for consistency
    app_name = "BoltQT"
    
    # Create and show loading screen first
    loading_screen = EnhancedLoadingScreen(app_name=app_name)
    
    # Show the loading screen
    loading_screen.show()
    loading_screen.set_progress(5, "Starting application...")
    app.processEvents()  # Process events to ensure loading screen appears before proceeding
    
    try:
        # Initialize main window with loading screen
        loading_screen.set_progress(20, "Creating main window...")
        app.processEvents()  # Process events to update UI
        main_window = MainWindow(loading_screen, app)  # Pass app instance here
        main_window.setWindowTitle(app_name)  # Use same app name for consistency
        
        # Position window in center of screen
        screen_geometry = app.primaryScreen().availableGeometry()
        x = (screen_geometry.width() - main_window.width()) // 2
        y = (screen_geometry.height() - main_window.height()) // 2
        main_window.move(x, y)
        
        # Show main window and enter Qt's event loop
        loading_screen.set_progress(90, "Ready to launch...")
        app.processEvents()  # Process events to update UI
        main_window.showMaximized()  # Open the window maximized
        main_window.activateWindow()  # Make sure the window takes focus
        main_window.raise_()  # Bring window to front
        
        # Return code from app execution
        return app.exec()
    except Exception as e:
        # Handle initialization errors
        import traceback
        error_msg = f"Error during startup: {str(e)}\n{traceback.format_exc()}"
        loading_screen.set_progress(100, "Error encountered!")
        app.processEvents()  # Process events to update UI
        # Display error in loading screen
        QMessageBox.critical(None, "Startup Error", error_msg)
        return 1

if __name__ == "__main__":
    sys.exit(main())