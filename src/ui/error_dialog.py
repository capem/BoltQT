from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from typing import Optional

from ..utils.logger import get_logger


class MacErrorDialog(QDialog):
    """Custom Mac-style error dialog."""

    def __init__(
        self, parent: Optional[QWidget], title: str, message: str, is_modal: bool = True
    ) -> None:
        """Show a Mac-styled error dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Error message to display.
            is_modal: If True, dialog blocks until dismissed. If False, dialog is non-modal.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        # Set modal state
        if is_modal:
            self.setWindowModality(Qt.WindowModality.ApplicationModal)
        else:
            self.setWindowModality(Qt.WindowModality.NonModal)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header with icon and title
        header_layout = QHBoxLayout()

        # Error icon
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        try:
            # Create warning/error icon (red circle with exclamation)
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)
            icon_label.setPixmap(pixmap)
        except Exception:
            # Fallback text if icon creation fails
            icon_label.setText("⚠️")
            icon_label.setFont(QFont("system-ui", 16))

        header_layout.addWidget(icon_label)

        # Title text
        title_label = QLabel(title)
        title_font = QFont("system-ui", 13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Message text
        message_browser = QTextBrowser()
        message_browser.setPlainText(message)
        message_browser.setFont(QFont("system-ui", 11))
        message_browser.setFrameStyle(0)  # No frame
        message_browser.setMinimumHeight(80)
        message_browser.setStyleSheet("background-color: transparent;")
        layout.addWidget(message_browser)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # OK button
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.setFixedWidth(80)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

        # Show the dialog if non-modal
        if not is_modal:
            self.show()


def show_error(
    parent: Optional[QWidget], context: str, error: Exception, is_modal: bool = True
) -> None:
    """Show an error dialog with formatted error message.

    Args:
        parent: Parent widget for the dialog.
        context: Context where the error occurred.
        error: The exception that was raised.
        is_modal: If True, dialog blocks until dismissed. If False, dialog is non-modal.
    """
    # Log the error
    logger = get_logger()
    error_msg = f"Error {context}: {str(error)}"
    logger.error(error_msg)

    # Create and show the dialog
    dialog = MacErrorDialog(
        parent, "Error", f"Error {context}:\n{str(error)}", is_modal=is_modal
    )

    if is_modal:
        dialog.exec()


def show_warning(parent: Optional[QWidget], context: str, message: str) -> None:
    """Show a non-modal warning dialog.

    Args:
        parent: Parent widget for the dialog.
        context: Context where the warning occurred.
        message: Warning message to display.
    """
    # Log the warning
    logger = get_logger()
    warning_msg = f"Warning {context}: {message}"
    logger.warning(warning_msg)

    # Create and show the dialog (no need to store reference as it shows itself)
    MacErrorDialog(
        parent, "Warning", f"Warning {context}:\n{message}", is_modal=False
    )
    # The dialog will show itself since is_modal=False
