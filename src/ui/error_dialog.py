from __future__ import annotations
from PyQt6.QtWidgets import QMessageBox, QWidget
from typing import Optional

class ErrorDialog:
    """Display error messages to the user."""
    
    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        message: str
    ) -> None:
        """Show an error dialog.
        
        Args:
            parent: Parent widget for the dialog.
            title: Dialog title.
            message: Error message to display.
        """
        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.setDefaultButton(QMessageBox.StandardButton.Ok)
        dialog.exec()

def show_error(parent: Optional[QWidget], context: str, error: Exception) -> None:
    """Show an error dialog with formatted error message.
    
    Args:
        parent: Parent widget for the dialog.
        context: Context where the error occurred.
        error: The exception that was raised.
    """
    ErrorDialog(
        parent,
        "Error",
        f"Error {context}:\n{str(error)}"
    )