from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)
from PyQt6.QtPdfWidgets import QPdfView
from PyQt6.QtCore import Qt, QEvent
from ..utils.pdf_manager import PDFManager


class PDFViewer(QWidget):
    """Widget for displaying PDF pages using QPdfView."""

    # Zoom levels (percentages)
    ZOOM_LEVELS = [25, 50, 75, 100, 125, 150, 175, 200]

    def __init__(
        self, pdf_manager: PDFManager, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        self.pdf_manager = pdf_manager
        self.current_pdf: Optional[str] = None
        self.zoom_level: float = 1.0

        # Create loading label first
        self.loading_label = QLabel("No PDF loaded", self)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("background: none; border: none;")

        # Initialize PDF components
        self.pdf_document = None  # Will be set from PDFManager's document

        # Create and configure PDF viewer widget
        self.pdf_view = QPdfView(self)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.zoom_level)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)

        # Enable touch and wheel events
        viewport = self.pdf_view.viewport()
        if viewport:
            viewport.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
            viewport.installEventFilter(self)

        # Create layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.pdf_view)
        layout.addWidget(self.loading_label)

        # Set stylesheet
        self.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QLabel {
                font-family: 'Segoe UI';
                font-size: 12pt;
            }
        """)

    def eventFilter(self, obj, event):
        """Handle events for child widgets."""
        if obj is self.pdf_view.viewport() and event.type() == QEvent.Type.Wheel:
            # Directly access the wheel event properties
            wheel_event = event  # The event is already a QWheelEvent

            # Check if Ctrl key is pressed during wheel event
            if wheel_event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = wheel_event.angleDelta().y()
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()

                # Accept the event to prevent further processing
                return True

            # Check if Shift key is pressed during wheel event for horizontal scrolling
            elif wheel_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Get the horizontal scroll bar
                h_scrollbar = self.pdf_view.horizontalScrollBar()
                if h_scrollbar and h_scrollbar.isVisible():
                    # Calculate scroll amount based on delta
                    delta = wheel_event.angleDelta().y()
                    # Use negative delta to match natural scroll direction
                    scroll_amount = -delta / 120 * 20  # Adjust scrolling speed
                    # Apply horizontal scrolling
                    h_scrollbar.setValue(h_scrollbar.value() + int(scroll_amount))

                    # Accept the event to prevent further processing
                    return True

        # Let the base class handle the event
        return super().eventFilter(obj, event)

    def clear_pdf(self) -> None:
        """Explicitly close and clear the current PDF document.

        This method properly releases all resources and file handles before clearing the PDF.
        It should be called before attempting to remove or modify the PDF file.
        """
        try:
            if self.pdf_document:
                # First remove document from view to prevent access during cleanup
                self.pdf_view.setDocument(None)
                
                # Only close/delete if it's not the manager's current document
                if self.pdf_document is not self.pdf_manager._current_doc:
                    try:
                        self.pdf_document.close()
                        self.pdf_document.deleteLater()
                    except Exception as e:
                        print(f"[DEBUG] Non-critical error cleaning up old document: {str(e)}")

            # Clear references
            self.pdf_document = None
            self.current_pdf = None

        except Exception as e:
            print(f"[DEBUG] Error during PDF cleanup: {str(e)}")

    def display_pdf(
        self,
        pdf_path: Optional[str],
        zoom: Optional[float] = None,
        show_loading: bool = True,
        retry_count: int = 3,
    ) -> None:
        """Display a PDF file with proper error handling and retries.

        Args:
            pdf_path: Path to the PDF file.
            zoom: Zoom level (1.0 = 100%).
            show_loading: Whether to show the loading label.
            retry_count: Number of times to retry loading if file is locked.
        """
        if show_loading:
            self.loading_label.show()
            self.loading_label.raise_()

        try:
            if not pdf_path:
                self.clear_pdf()
                return

            # Update zoom level if provided
            if zoom is not None:
                self.zoom_level = zoom
                self.pdf_view.setZoomFactor(self.zoom_level)

            # Try opening the PDF with retries
            for attempt in range(retry_count):
                try:
                    # First load via PDFManager to get new document
                    if not self.pdf_manager.open_pdf(pdf_path):
                        raise Exception("Failed to open PDF via PDFManager")
                    
                    # Store new document reference before clearing old one
                    new_document = self.pdf_manager._current_doc
                    
                    # Now safe to clear old document
                    self.clear_pdf()
                    
                    # Set new document
                    self.pdf_document = new_document
                    self.pdf_view.setDocument(self.pdf_document)

                    # Update current PDF path only after successful load
                    self.current_pdf = pdf_path
                    break

                except Exception as e:
                    if attempt < retry_count - 1:
                        print(
                            f"[DEBUG] Retry {attempt + 1}: Error loading PDF: {str(e)}"
                        )
                        import time

                        time.sleep(0.5)  # Short delay between retries
                        continue
                    raise  # Re-raise the last exception if all retries failed

        except Exception as e:
            error_msg = f"Error displaying PDF: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            self.loading_label.setText(f"{error_msg}\n\nPlease try again.")
            self.loading_label.show()
            self.current_pdf = None  # Ensure we don't keep reference to failed load

        finally:
            # Hide loading label if successful
            if show_loading and self.current_pdf:
                self.loading_label.hide()

    def zoom_in(self) -> None:
        """Zoom in to the next zoom level."""
        current_percent = int(self.zoom_level * 100)
        for level in self.ZOOM_LEVELS:
            if level > current_percent:
                self.zoom_level = level / 100
                self.pdf_view.setZoomFactor(self.zoom_level)
                break

    def zoom_out(self) -> None:
        """Zoom out to the previous zoom level."""
        current_percent = int(self.zoom_level * 100)
        for level in reversed(self.ZOOM_LEVELS):
            if level < current_percent:
                self.zoom_level = level / 100
                self.pdf_view.setZoomFactor(self.zoom_level)
                break
