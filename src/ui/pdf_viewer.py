from __future__ import annotations
from typing import Optional, Tuple
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfPageSelector, QPdfView
from PyQt6.QtCore import Qt, QEvent
from ..utils.pdf_manager import PDFManager

class PDFViewer(QWidget):
    """Widget for displaying PDF pages using QPdfView."""
    
    # Zoom levels (percentages)
    ZOOM_LEVELS = [25, 50, 75, 100, 125, 150, 175, 200]
    
    def __init__(self, pdf_manager: PDFManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self.pdf_manager = pdf_manager
        self.current_pdf: Optional[str] = None
        self.zoom_level: float = 1.0
        
        # Create PDF document object
        self.pdf_document = QPdfDocument(self)
        
        # Create PDF viewer widget
        self.pdf_view = QPdfView(self)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.zoom_level)
        
        # Set the document view mode to display all pages vertically with scroll bar
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        
        # Enable viewport events for the PDF view to allow wheel events
        self.pdf_view.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.pdf_view.viewport().installEventFilter(self)
        
        # Create loading label
        self.loading_label = QLabel("Loading...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.hide()
        
        # Create page selector
        self.page_selector = QPdfPageSelector(self)
        self.page_selector.setDocument(self.pdf_document)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.pdf_view)
        layout.addWidget(self.loading_label)
        layout.addWidget(self.page_selector)
        
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
    
    def display_pdf(
        self,
        pdf_path: Optional[str],
        zoom: Optional[float] = None,
        show_loading: bool = True
    ) -> None:
        """Display a PDF file.
        
        Args:
            pdf_path: Path to the PDF file.
            zoom: Zoom level (1.0 = 100%).
            show_loading: Whether to show the loading label.
        """
        try:
            # Clear current display
            self.pdf_document.close()
            self.current_pdf = None
            
            if not pdf_path:
                return
            
            # Show loading label if requested
            if show_loading:
                self.loading_label.show()
                self.loading_label.raise_()
            
            # Update zoom level if provided
            if zoom is not None:
                self.zoom_level = zoom
                self.pdf_view.setZoomFactor(self.zoom_level)
            
            # Open the PDF using PDF manager to track it
            if not self.pdf_manager.open_pdf(pdf_path):
                raise RuntimeError("Failed to open PDF")
            
            # Load the document in QPdfView
            self.pdf_document.load(pdf_path)
            
            # Update current PDF path
            self.current_pdf = pdf_path
            
        except Exception as e:
            print(f"[DEBUG] Error displaying PDF: {str(e)}")
            self.loading_label.setText(f"Error displaying PDF:\n{str(e)}")
            self.loading_label.show()
            
        finally:
            # Hide loading label if it was shown
            if show_loading:
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
    
    def get_visible_rect(self) -> Tuple[int, int, int, int]:
        """Get the currently visible rectangle in the viewer."""
        viewport = self.pdf_view.viewport()
        return (0, 0, viewport.width(), viewport.height())