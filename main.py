#!/usr/bin/env python3
from __future__ import annotations

import sys
import os
import traceback
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStatusBar,
    QWidget,
    QVBoxLayout,
    QMessageBox,
)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal

from src.ui.config_tab import ConfigTab
from src.ui.processing_tab import ProcessingTab
from src.ui.loading_screen import EnhancedLoadingScreen
from src.ui.mac_style import apply_mac_style
from src.ui.mac_tab_widget import MacTabWidget
from src.utils.config_manager import ConfigManager
from src.utils.excel_manager import ExcelManager
from src.utils.pdf_manager import PDFManager
from src.utils.vision_manager import VisionManager
from src.utils.widget_debugger import setup_global_debug_shortcut
from src.utils.logger import get_logger, setup_logger
from src.ui.error_dialog import show_error

class MainWindow(QMainWindow):
    """Main window of the application."""

    def __init__(
        self, loading_screen: EnhancedLoadingScreen, app: QApplication
    ) -> None:
        super().__init__()

        # Store loading screen reference
        self.loading_screen = loading_screen
        self.app = app  # Store app reference

        # These will be initialized later by the thread
        self.config_manager = None
        self.excel_manager = None
        self.pdf_manager = None
        self.vision_manager = None

        # Create initialization thread
        self.init_thread = InitializationThread()
        self.init_thread.progress_signal.connect(self.update_loading_progress)
        self.init_thread.finished_signal.connect(self.on_init_complete)
        self.init_thread.error_signal.connect(self.on_init_error)

        # Start the initialization thread
        self.init_thread.start()

        # Set window properties immediately (doesn't need to wait for managers)
        self.loading_screen.set_progress(20, "Setting up main window...")
        self.setMinimumSize(1200, 800)

        # Create central widget and layout immediately
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Create layout for central widget
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget using MacTabWidget
        self.tab_widget = MacTabWidget()
        self.layout.addWidget(self.tab_widget)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Initializing...")

        # Set up widget debugging shortcut
        setup_global_debug_shortcut(self)

    def handle_error(self, error: Exception, context: str) -> None:
        """Handle errors in the application."""
        logger = get_logger()

        # Log the error with appropriate level
        error_msg = f"{context}: {str(error)}"

        # For certain errors like OSError accessing network files,
        # we want to avoid blocking the application
        if isinstance(error, OSError) and (
            "//192.168.0.77" in str(error) or "\\\\192.168.0.77" in str(error)
        ):
            # Log as warning since it's non-critical
            logger.warning(f"Network file access error: {error_msg}")

            # Update status bar without showing dialog
            self.status_bar.showMessage(f"Error accessing network file: {str(error)}")
            return

        # For other errors, log as error and show the dialog
        logger.error(error_msg)
        if hasattr(error, "__traceback__"):
            logger.error(f"Traceback: {traceback.format_exception(type(error), error, error.__traceback__)}")

        # Show error dialog to user
        show_error(self, context, error)

    def handle_status(self, message: str) -> None:
        """Update status bar with message and log it."""

        # Log status message at info level
        get_logger().info(f"Status: {message}")

        # Update status bar
        self.status_bar.showMessage(message)

    def update_loading_progress(self, progress: int, message: str) -> None:
        """Update loading screen with progress from the initialization thread."""

        # Log progress at debug level
        get_logger().debug(f"Loading progress: {progress}% - {message}")

        # Update loading screen
        self.loading_screen.set_progress(progress, message)

    def on_init_complete(self, config_manager, excel_manager, pdf_manager, vision_manager) -> None:
        """Handle completion of the initialization thread."""
        logger = get_logger()

        logger.info("Initialization completed, setting up main window")

        # Store the initialized managers
        self.config_manager = config_manager
        self.excel_manager = excel_manager
        self.pdf_manager = pdf_manager
        self.vision_manager = vision_manager

        # Now that we have managers, we can create the tabs
        logger.debug("Creating configuration tab")
        self.loading_screen.set_progress(60, "Creating configuration tab...")
        self.config_tab = ConfigTab(
            self.config_manager,
            self.excel_manager,
            self.handle_error,
            self.handle_status,
        )

        logger.debug("Creating processing tab")
        self.loading_screen.set_progress(75, "Creating processing tab...")
        self.processing_tab = ProcessingTab(
            self.config_manager,
            self.excel_manager,
            self.pdf_manager,
            self.vision_manager,  # Directly pass vision_manager as a separate dependency
            self.handle_error,
            self.handle_status,
        )

        # Add tabs
        logger.debug("Adding tabs to main window")
        self.loading_screen.set_progress(85, "Finalizing UI setup...")
        self.tab_widget.addTab(self.processing_tab, "Processing")
        self.tab_widget.addTab(self.config_tab, "Configuration")

        # Update status bar
        self.status_bar.showMessage("Ready")
        logger.info("Application ready")

        # Show the main window now that initialization is complete
        logger.debug("Showing main window")
        self.loading_screen.set_progress(95, "Showing main window...")
        self.showMaximized()  # Open the window maximized
        self.activateWindow()  # Make sure the window takes focus
        self.raise_()  # Bring window to front

        # Hide loading screen after a short delay to ensure smooth transition
        self.loading_screen.set_progress(100, "Ready!")
        QTimer.singleShot(800, self.loading_screen.hide)

    def on_init_error(self, error: Exception) -> None:
        """Handle errors from the initialization thread."""

        logger = get_logger()

        # Log the error with traceback
        logger.error(f"Initialization error: {str(error)}")
        if hasattr(error, "__traceback__"):
            logger.error(f"Traceback: {traceback.format_exception(type(error), error, error.__traceback__)}")

        # Show error dialog
        show_error(self, "Initialization Error", error)

        # Update loading screen and hide it after a delay
        self.loading_screen.set_progress(100, "Error during initialization!")
        QTimer.singleShot(2000, self.loading_screen.hide)


class InitializationThread(QThread):
    """Thread for handling heavy initialization tasks without blocking the UI thread."""

    # Signals for progress reporting and completion
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(
        object, object, object, object
    )  # ConfigManager, ExcelManager, PDFManager, VisionManager
    error_signal = pyqtSignal(Exception)

    def __init__(self):
        super().__init__()

    def run(self):
        logger = get_logger()

        try:
            logger.info("Starting initialization thread")

            # Initialize managers in the background thread
            self.progress_signal.emit(25, "Initializing configuration manager...")
            logger.debug("Initializing configuration manager")
            config_manager = ConfigManager()
            config = config_manager.get_config() # Get config early for paths

            self.progress_signal.emit(35, "Initializing Excel manager...")
            logger.debug("Initializing Excel manager")
            excel_manager = ExcelManager()

            # Initial load of excel data if configured
            excel_file = config.get("excel_file")
            excel_sheet = config.get("excel_sheet")
            if excel_file and excel_sheet:
                try:
                    self.progress_signal.emit(38, "Loading initial Excel data...")
                    logger.debug(f"Loading initial Excel data from {excel_file}, sheet: {excel_sheet}")
                    excel_manager.load_excel_data(excel_file, excel_sheet)
                except Exception as excel_load_err:
                    logger.warning(f"Initial Excel load failed: {excel_load_err}")
                    # Don't block initialization, but log the warning

            self.progress_signal.emit(45, "Initializing PDF manager...")
            logger.debug("Initializing PDF manager")
            pdf_manager = PDFManager()

            self.progress_signal.emit(48, "Initializing Vision manager...")
            logger.debug("Initializing Vision manager")
            vision_manager = VisionManager(config_manager)

            # Preload hyperlinks if Excel data was loaded
            if excel_manager.excel_data is not None and excel_file and excel_sheet:
                self.progress_signal.emit(50, "Caching hyperlinks...")
                logger.debug("Starting hyperlink caching")
                try:
                    # Define a callback to update progress (e.g., from 50% to 58%)
                    def hyperlink_progress(percent: int):
                        self.progress_signal.emit(50 + int(percent * 0.08), f"Caching hyperlinks ({percent}%)...")
                        if percent % 25 == 0:  # Log at 0%, 25%, 50%, 75%, 100%
                            logger.debug(f"Hyperlink caching progress: {percent}%")

                    excel_manager.preload_hyperlinks_async(
                        excel_file, excel_sheet, progress_callback=hyperlink_progress
                    )
                    self.progress_signal.emit(58, "Hyperlink caching complete.")
                    logger.debug("Hyperlink caching completed successfully")
                except Exception as cache_err:
                    logger.warning(f"Hyperlink caching failed: {cache_err}")
                    # Log warning, don't block initialization
                    self.progress_signal.emit(58, "Hyperlink caching failed (continuing).")
            else:
                # Skip caching progress if no Excel data
                logger.debug("Skipping hyperlink caching (no Excel data)")
                self.progress_signal.emit(58, "Skipping hyperlink caching (no Excel data).")

            # Signal that initialization is complete and pass the managers back
            logger.info("Initialization thread completed successfully")
            self.progress_signal.emit(59, "Initialization complete!") # Adjusted percentage
            self.finished_signal.emit(config_manager, excel_manager, pdf_manager, vision_manager)

        except Exception as e:
            # Log the error
            logger.error(f"Error in initialization thread: {str(e)}")
            if hasattr(e, "__traceback__"):
                logger.error(f"Traceback: {traceback.format_exception(type(e), e, e.__traceback__)}")

            # Signal if there's an error during initialization
            self.error_signal.emit(e)


def main() -> int:
    # Application name - define once for consistency
    app_name = "BoltQT"

    # Initialize logger first
    logger = setup_logger(
        app_name,
        log_dir=os.path.join(os.path.expanduser("~"), "BoltQT", "logs")
    )
    logger.info(f"Starting {app_name} application")

    # Create application
    logger.debug("Initializing QApplication")
    app = QApplication(sys.argv)

    # Process events before creating loading screen to ensure UI is responsive
    app.processEvents()

    # Apply Mac-inspired styling
    logger.debug("Applying application styling")
    apply_mac_style(app)

    # Create loading screen with pre-set progress to avoid empty initial display
    logger.debug("Creating loading screen")
    loading_screen = EnhancedLoadingScreen(app_name=app_name)
    loading_screen.progress = 5  # Set initial progress directly
    loading_screen.progress_text = "Starting application..."

    # Show immediately and force paint
    loading_screen.show()
    app.processEvents()  # First process event to make sure it's visible
    loading_screen.update()  # Force immediate repaint
    app.processEvents()  # Second process event to ensure paint completes

    try:
        # Initialize main window with loading screen
        logger.debug("Creating main window")
        loading_screen.set_progress(15, "Creating main window...")
        main_window = MainWindow(loading_screen, app)  # Pass app instance here
        main_window.setWindowTitle(app_name)  # Use same app name for consistency

        # Position window in center of screen
        screen_geometry = app.primaryScreen().availableGeometry()
        x = (screen_geometry.width() - main_window.width()) // 2
        y = (screen_geometry.height() - main_window.height()) // 2
        main_window.move(x, y)
        logger.debug(f"Positioned window at x={x}, y={y}")

        # Don't show the main window yet - it will be shown when initialization completes
        # The loading screen will be visible during the entire initialization process

        # Return code from app execution
        logger.info("Starting application main loop")
        return app.exec()
    except Exception as e:
        # Handle initialization errors
        error_trace = traceback.format_exc()
        error_msg = f"Error during startup: {str(e)}\n{error_trace}"

        # Log the error with full traceback
        logger.critical(f"Fatal error during application startup: {str(e)}")
        logger.critical(f"Traceback: {error_trace}")

        # Update loading screen
        loading_screen.set_progress(100, "Error encountered!")
        app.processEvents()  # Process events to update UI

        # Display error in loading screen
        QMessageBox.critical(None, "Startup Error", error_msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
