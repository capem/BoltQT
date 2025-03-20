from __future__ import annotations
from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import Qt
from typing import Optional


class ErrorDialog:
    """Display error messages to the user."""

    def __init__(
        self, 
        parent: Optional[QWidget], 
        title: str, 
        message: str,
        is_modal: bool = True
    ) -> None:
        """Show an error dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Error message to display.
            is_modal: If True, dialog blocks until dismissed. If False, dialog is non-modal.
        """
        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        if not is_modal:
            dialog.setWindowModality(Qt.WindowModality.NonModal)
            dialog.show()
        else:
            dialog.exec()


def show_error(
    parent: Optional[QWidget], 
    context: str, 
    error: Exception,
    is_modal: bool = True
) -> None:
    """Show an error dialog with formatted error message.

    Args:
        parent: Parent widget for the dialog.
        context: Context where the error occurred.
        error: The exception that was raised.
        is_modal: If True, dialog blocks until dismissed. If False, dialog is non-modal.
    """
    ErrorDialog(parent, "Error", f"Error {context}:\n{str(error)}", is_modal=is_modal)


def show_warning(
    parent: Optional[QWidget],
    context: str,
    message: str
) -> None:
    """Show a non-modal warning dialog.
    
    Args:
        parent: Parent widget for the dialog.
        context: Context where the warning occurred.
        message: Warning message to display.
    """
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setWindowTitle("Warning")
    dialog.setText(f"Warning {context}:\n{message}")
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.setDefaultButton(QMessageBox.StandardButton.Ok)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.show()
