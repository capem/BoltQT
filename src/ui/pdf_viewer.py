from __future__ import annotations
from typing import Optional, Tuple
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QScrollArea,
    QFrame,
)
from PyQt6.QtGui import QPixmap, QImage, QTransform
from PyQt6.QtCore import Qt, QSize
import fitz  # PyMuPDF
from ..utils.pdf_manager import PDFManager

class PDFViewer(QScrollArea):
    """Widget for displaying PDF pages."""
    
    # Zoom levels (percentages)
    ZOOM_LEVELS = [25, 50, 75, 100, 125, 150, 175, 200]
    
    def __init__(self, pdf_manager: PDFManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self.pdf_manager = pdf_manager
        self.current_image: Optional[QPixmap] = None
        self.current_pdf: Optional[str] = None
        self.zoom_level: float = 1.0
        
        # Create display widget
        self.display_widget = QLabel()
        self.display_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_widget.setMinimumSize(QSize(200, 200))
        
        # Create loading label
        self.loading_label = QLabel("Loading...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.hide()
        
        # Create container widget
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.display_widget)
        layout.addWidget(self.loading_label)
        
        # Configure scroll area
        self.setWidget(container)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Set stylesheet
        self.setStyleSheet("""
            QScrollArea {
                background: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QLabel {
                font-family: 'Segoe UI';
                font-size: 12pt;
            }
        """)
    
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
            self.display_widget.clear()
            self.current_image = None
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
            
            # Open the PDF
            if not self.pdf_manager.open_pdf(pdf_path):
                raise RuntimeError("Failed to open PDF")
            
            # Get the first page
            page = self.pdf_manager.get_current_page()
            if not page:
                raise RuntimeError("Failed to get PDF page")
            
            # Calculate zoom and rotation
            zoom_matrix = fitz.Matrix(self.zoom_level, self.zoom_level)
            rotation = self.pdf_manager.get_rotation()
            if rotation:
                zoom_matrix = zoom_matrix * fitz.Matrix(rotation)
            
            # Render page to pixmap
            pix = page.get_pixmap(matrix=zoom_matrix)
            
            # Convert to QImage
            img = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888
            )
            
            # Convert to QPixmap and apply rotation
            pixmap = QPixmap.fromImage(img)
            if rotation:
                transform = QTransform()
                transform.rotate(rotation)
                pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
            
            # Update display
            self.current_image = pixmap
            self.current_pdf = pdf_path
            self.display_widget.setPixmap(pixmap)
            
        except Exception as e:
            print(f"[DEBUG] Error displaying PDF: {str(e)}")
            self.display_widget.setText(f"Error displaying PDF:\n{str(e)}")
            
        finally:
            # Hide loading label
            self.loading_label.hide()
    
    def zoom_in(self) -> None:
        """Zoom in to the next zoom level."""
        current_percent = int(self.zoom_level * 100)
        for level in self.ZOOM_LEVELS:
            if level > current_percent:
                self.zoom_level = level / 100
                self.display_pdf(self.current_pdf, show_loading=False)
                break
    
    def zoom_out(self) -> None:
        """Zoom out to the previous zoom level."""
        current_percent = int(self.zoom_level * 100)
        for level in reversed(self.ZOOM_LEVELS):
            if level < current_percent:
                self.zoom_level = level / 100
                self.display_pdf(self.current_pdf, show_loading=False)
                break
    
    def get_visible_rect(self) -> Tuple[int, int, int, int]:
        """Get the currently visible rectangle in the scroll area."""
        return (
            self.horizontalScrollBar().value(),
            self.verticalScrollBar().value(),
            self.viewport().width(),
            self.viewport().height()
        )