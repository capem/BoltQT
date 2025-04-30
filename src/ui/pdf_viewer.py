from __future__ import annotations

import time
import traceback
from typing import List, Optional

import fitz  # PyMuPDF
from PyQt6.QtCore import QEvent, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QImage,
    QKeySequence,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.logger import get_logger
from ..utils.pdf_manager import PDFManager


class PageWidget(QLabel):
    """Widget for displaying a single PDF page."""

    def __init__(self, page_num: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.page_num = page_num
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "margin: 8px; background-color: white; border: 1px solid #e0e0e0; border-radius: 2px;"
        )
        # Remove minimum width constraint to let the PDF render at its natural size
        # self.setMinimumWidth(600)


class MultiPageWidget(QWidget):
    """Container for all PDF page widgets."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(
            24
        )  # Increase space between pages for better readability
        self.layout.setContentsMargins(20, 20, 20, 20)  # More generous margins
        self.layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
        )  # Center pages horizontally
        self.page_widgets: List[PageWidget] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Set a light gray background for the area around pages
        self.setStyleSheet("background-color: #f5f5f5;")


class PDFViewer(QWidget):
    """Enhanced widget for displaying PDF pages with zoom and rotation controls using PyMuPDF."""

    # Signals for communication with parent widgets
    pdfLoaded = pyqtSignal(bool)
    pageChanged = pyqtSignal(int, int)  # current page, total pages

    # Zoom levels (percentages)
    ZOOM_LEVELS = [25, 50, 75, 100, 125, 150, 175, 200, 300, 400, 500]
    # Rotation angles (degrees)
    ROTATION_ANGLES = [0, 90, 180, 270]

    def __init__(
        self, pdf_manager: PDFManager, parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the PDF viewer with PyMuPDF integration.

        Args:
            pdf_manager: Manager for PDF operations
            parent: Parent widget
        """
        super().__init__(parent)

        self.pdf_manager = pdf_manager
        # Register this viewer with the manager for callbacks
        self.pdf_manager._viewer_ref = self

        self.current_pdf: Optional[str] = None
        self.zoom_level: float = 1.0
        self.rotation_angle: int = 0
        self.current_page: int = 0  # Used for page indicator
        self.total_pages: int = 0

        # PyMuPDF document
        self.doc: Optional[fitz.Document] = None

        # Flag to track when we're programmatically scrolling
        self._programmatic_scroll = False

        # Initialize UI components
        self._init_ui()
        self._setup_shortcuts()

        # Set initial state
        self._update_ui_state(False)

        # Connect scroll signals
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _init_ui(self) -> None:
        """Initialize all UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create toolbar with controls
        self.toolbar = self._create_toolbar()
        main_layout.addWidget(self.toolbar)

        # Create scroll area for continuous PDF viewing
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setStyleSheet("background-color: #f0f0f0;")

        # Create multi-page container
        self.page_container = MultiPageWidget()
        self.scroll_area.setWidget(self.page_container)

        # Enable touch and wheel events for scrolling
        self.scroll_area.viewport().setAttribute(
            Qt.WidgetAttribute.WA_AcceptTouchEvents, True
        )
        self.scroll_area.viewport().installEventFilter(self)

        # Add widgets to layout
        main_layout.addWidget(self.scroll_area)

        # Set stylesheets
        self.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #ccc;
                border-radius: 5px;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            /* Style for spacer widgets */
            QWidget[objectName^="spacer"] {
                background: transparent;
                border: none;
            }
            QToolBar {
                background: #f0f0f0;
                border-bottom: 1px solid #ccc;
                border-top: none;
                border-left: none;
                border-right: none;
                border-radius: 0px;
                padding: 2px;
            }
            QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 3px;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QToolButton:hover {
                background: #e0e0e0;
                border: 1px solid #ccc;
            }
            QToolButton:pressed {
                background: #d0d0d0;
            }
            QLabel {
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QComboBox {
                padding: 2px 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background: white;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QPushButton {
                font-family: 'Segoe UI';
                font-size: 10pt;
                padding: 4px 8px;
            }
            QSlider {
                font-family: 'Segoe UI';
            }
            QScrollArea {
                background: #f0f0f0;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: #f0f0f0;
            }
        """)

    def _create_toolbar(self) -> QToolBar:
        """Create a toolbar with navigation and zoom controls."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f9f9f9;
                border-bottom: 1px solid #e0e0e0;
                spacing: 5px;
                padding: 2px;
            }

            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px;
                margin: 2px;
            }

            QToolButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #e0e0e0;
            }

            QToolButton:pressed {
                background-color: #e0e0e0;
            }

            QLabel {
                margin: 0 10px;
                color: #505050;
            }
        """)

        # Create a spacer widget for the left side
        left_spacer = QWidget()
        left_spacer.setObjectName("spacer_left")
        left_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar.addWidget(left_spacer)

        # Page indicator
        self.page_indicator = QLabel("0 / 0")
        self.page_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_indicator.setMinimumWidth(80)
        toolbar.addWidget(self.page_indicator)

        toolbar.addSeparator()

        # Zoom controls
        self.zoom_out_btn = QToolButton()
        self.zoom_out_btn.setText("-")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(self.zoom_out_btn)

        self.zoom_in_btn = QToolButton()
        self.zoom_in_btn.setText("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(self.zoom_in_btn)

        toolbar.addSeparator()

        # Rotation controls
        self.rotate_left_btn = QToolButton()
        self.rotate_left_btn.setText("↺")
        self.rotate_left_btn.setToolTip("Rotate Left")
        self.rotate_left_btn.clicked.connect(self.rotate_left)
        toolbar.addWidget(self.rotate_left_btn)

        self.rotate_right_btn = QToolButton()
        self.rotate_right_btn.setText("↻")
        self.rotate_right_btn.setToolTip("Rotate Right")
        self.rotate_right_btn.clicked.connect(self.rotate_right)
        toolbar.addWidget(self.rotate_right_btn)

        toolbar.addSeparator()

        # Fit controls
        self.fit_width_btn = QToolButton()
        self.fit_width_btn.setText("Fit Width")
        self.fit_width_btn.setToolTip("Fit to Width")
        self.fit_width_btn.clicked.connect(self.fit_width)
        toolbar.addWidget(self.fit_width_btn)

        self.fit_page_btn = QToolButton()
        self.fit_page_btn.setText("Fit Page")
        self.fit_page_btn.setToolTip("Fit to Page")
        self.fit_page_btn.clicked.connect(self.fit_page)
        toolbar.addWidget(self.fit_page_btn)

        # Create a spacer widget for the right side
        right_spacer = QWidget()
        right_spacer.setObjectName("spacer_right")
        right_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar.addWidget(right_spacer)

        return toolbar

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        # Page navigation shortcuts
        self.prev_action = QAction("Previous Page", self)
        self.prev_action.setShortcut(QKeySequence.StandardKey.MoveToPreviousPage)
        self.prev_action.triggered.connect(self.previous_page)
        self.addAction(self.prev_action)

        self.next_action = QAction("Next Page", self)
        self.next_action.setShortcut(QKeySequence.StandardKey.MoveToNextPage)
        self.next_action.triggered.connect(self.next_page)
        self.addAction(self.next_action)

        # Zoom shortcuts
        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut(QKeySequence("Ctrl++"))
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.addAction(self.zoom_out_action)

        # Rotation shortcuts
        self.rotate_left_action = QAction("Rotate Left", self)
        self.rotate_left_action.setShortcut(QKeySequence("Ctrl+["))
        self.rotate_left_action.triggered.connect(self.rotate_left)
        self.addAction(self.rotate_left_action)

        self.rotate_right_action = QAction("Rotate Right", self)
        self.rotate_right_action.setShortcut(QKeySequence("Ctrl+]"))
        self.rotate_right_action.triggered.connect(self.rotate_right)
        self.addAction(self.rotate_right_action)

        # Jump to first/last page
        self.first_page_action = QAction("First Page", self)
        self.first_page_action.setShortcut(QKeySequence("Home"))
        self.first_page_action.triggered.connect(lambda: self.jump_to_page(0))
        self.addAction(self.first_page_action)

        self.last_page_action = QAction("Last Page", self)
        self.last_page_action.setShortcut(QKeySequence("End"))
        self.last_page_action.triggered.connect(
            lambda: self.jump_to_page(self.total_pages - 1)
        )
        self.addAction(self.last_page_action)

    def eventFilter(self, obj, event):
        """Handle events for child widgets."""
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Type.Wheel:
            # Directly access the wheel event properties
            wheel_event = event  # The event is already a QWheelEvent

            # Check if Ctrl key is pressed during wheel event for zooming
            if wheel_event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = wheel_event.angleDelta().y()
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()
                return True

            # Check if Shift key is pressed during wheel event for horizontal scrolling
            elif wheel_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                delta = wheel_event.angleDelta().y()
                h_scrollbar = self.scroll_area.horizontalScrollBar()
                if h_scrollbar and h_scrollbar.isVisible():
                    # Use negative delta to match natural scroll direction
                    scroll_amount = -delta / 120 * 20  # Adjust scrolling speed
                    h_scrollbar.setValue(h_scrollbar.value() + int(scroll_amount))
                return True

        # Let the base class handle the event
        return super().eventFilter(obj, event)

    def _on_scroll(self, value):
        """Update current page indicator based on scroll position."""
        if (
            not self.doc
            or not self.page_container.page_widgets
            or self._programmatic_scroll
        ):
            return

        # Find the page that's most visible in the viewport
        viewport_rect = QRect(
            0,
            self.scroll_area.verticalScrollBar().value(),
            self.scroll_area.viewport().width(),
            self.scroll_area.viewport().height(),
        )

        best_visible_area = 0
        visible_page = 0

        for i, page_widget in enumerate(self.page_container.page_widgets):
            # Get page position relative to scroll area
            page_pos = page_widget.mapTo(self.scroll_area, page_widget.pos())
            page_rect = QRect(
                page_pos.x(), page_pos.y(), page_widget.width(), page_widget.height()
            )

            # Calculate intersection with viewport
            intersection = viewport_rect.intersected(page_rect)
            visible_area = intersection.width() * intersection.height()

            if visible_area > best_visible_area:
                best_visible_area = visible_area
                visible_page = i

        # Update current page if changed
        if visible_page != self.current_page:
            self.current_page = visible_page
            self._update_page_indicator()
            self.pageChanged.emit(self.current_page, self.total_pages)

    def clear_pdf(self) -> None:
        """Explicitly close and clear the current PDF document."""
        try:
            # Clear the PyMuPDF document
            if self.doc:
                self.doc.close()
                self.doc = None

            # Clear references
            current_path = self.current_pdf
            self.current_pdf = None
            self.current_page = 0
            self.total_pages = 0

            # Clear page widgets
            while self.page_container.layout.count():
                item = self.page_container.layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.page_container.page_widgets.clear()

            # Update UI
            self._update_page_indicator()
            self._update_ui_state(False)

            # Notify the PDF manager that we've released this file
            if self.pdf_manager and current_path:
                self.pdf_manager.close_current_pdf()

            logger = get_logger()
            logger.debug(f"PDF cleared and resources released: {current_path}")

        except Exception as e:
            logger = get_logger()
            logger.error(f"Error during PDF cleanup: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def display_pdf(
        self,
        pdf_path: Optional[str],
        zoom: Optional[float] = None,
        rotation: Optional[int] = None,
        page: int = 0,
        show_loading: bool = True,
        retry_count: int = 3,
    ) -> None:
        """Display a PDF file with proper error handling and retries.

        Args:
            pdf_path: Path to the PDF file.
            zoom: Zoom level (1.0 = 100%).
            rotation: Rotation angle in degrees (0, 90, 180, 270).
            page: Page number to display (0-indexed).
            show_loading: Whether to show the loading label.
            retry_count: Number of times to retry loading if file is locked.
        """
        try:
            if not pdf_path:
                self.clear_pdf()
                return

            # Update zoom level if provided
            if zoom is not None:
                self.zoom_level = zoom

            # Update rotation if provided
            if rotation is not None and rotation in self.ROTATION_ANGLES:
                self.rotation_angle = rotation

            # Try opening the PDF with retries
            for attempt in range(retry_count):
                try:
                    # Clear any existing document first
                    self.clear_pdf()

                    # Load PDF with PyMuPDF
                    self.doc = fitz.open(pdf_path)
                    self.total_pages = len(self.doc)

                    # Update current PDF path
                    self.current_pdf = pdf_path

                    # Render all pages
                    self._render_all_pages()

                    # Jump to specified page
                    self.jump_to_page(page if page < self.total_pages else 0)

                    # Update UI state
                    self._update_ui_state(True)

                    # Emit signal that PDF loaded successfully
                    self.pdfLoaded.emit(True)
                    break

                except Exception as e:
                    if attempt < retry_count - 1:
                        logger = get_logger()
                        logger.warning(
                            f"Retry {attempt + 1}: Error loading PDF: {str(e)}"
                        )
                        time.sleep(0.5)  # Short delay between retries
                        continue
                    raise  # Re-raise the last exception if all retries failed

        except Exception as e:
            logger = get_logger()
            error_msg = f"Error displaying PDF: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.current_pdf = None  # Ensure we don't keep reference to failed load
            self.pdfLoaded.emit(False)

    def _render_all_pages(self) -> None:
        """Render all pages of the PDF document."""
        if not self.doc:
            return

        try:
            # Clear previous pages
            while self.page_container.layout.count():
                item = self.page_container.layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.page_container.page_widgets.clear()

            # Create widgets for each page
            for page_num in range(self.total_pages):
                page_widget = PageWidget(page_num)
                self.page_container.layout.addWidget(page_widget)
                self.page_container.page_widgets.append(page_widget)

                # Render the page
                self._render_page(page_num)

            # Update page indicator
            self._update_page_indicator()

        except Exception as e:
            logger = get_logger()
            logger.error(f"Error rendering PDF pages: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _render_page(self, page_num: int) -> None:
        """Render a specific page of the PDF document.

        Args:
            page_num: The page number to render (0-indexed)
        """
        if not self.doc or page_num < 0 or page_num >= self.total_pages:
            return

        try:
            # Get the page widget
            if page_num >= len(self.page_container.page_widgets):
                logger = get_logger()
                logger.warning(f"Page widget not found for page {page_num}")
                return

            page_widget = self.page_container.page_widgets[page_num]

            # Get the PyMuPDF page
            page = self.doc[page_num]

            # Apply zoom level
            zoom_matrix = fitz.Matrix(self.zoom_level, self.zoom_level)

            # Apply rotation - fixed to use proper rotation method
            if self.rotation_angle:
                # PyMuPDF requires rotation in degrees
                zoom_matrix = zoom_matrix * fitz.Matrix(self.rotation_angle)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)

            # Convert pixmap to QImage
            img = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888,
            )

            # Convert QImage to QPixmap
            pixmap = QPixmap.fromImage(img)

            # Update the page widget
            page_widget.setPixmap(pixmap)
            # Set the exact size of the pixmap so it doesn't stretch
            page_widget.setFixedSize(pixmap.size())

        except Exception as e:
            logger = get_logger()
            logger.error(f"Error rendering page {page_num}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            if page_num < len(self.page_container.page_widgets):
                self.page_container.page_widgets[page_num].setText(
                    f"Error rendering page {page_num + 1}:\n{str(e)}"
                )

    def _update_page_indicator(self) -> None:
        """Update the page indicator label."""
        if self.total_pages > 0:
            self.page_indicator.setText(f"{self.current_page + 1} / {self.total_pages}")
        else:
            self.page_indicator.setText("0 / 0")

    def _update_ui_state(self, has_pdf: bool) -> None:
        """Update UI controls based on PDF loaded state."""
        # Enable/disable controls based on PDF state
        self.zoom_in_btn.setEnabled(has_pdf)
        self.zoom_out_btn.setEnabled(has_pdf)
        self.rotate_left_btn.setEnabled(has_pdf)
        self.rotate_right_btn.setEnabled(has_pdf)
        self.fit_width_btn.setEnabled(has_pdf)
        self.fit_page_btn.setEnabled(has_pdf)

    def zoom_in(self) -> None:
        """Zoom in to the next zoom level."""
        current_percent = int(self.zoom_level * 100)
        for level in self.ZOOM_LEVELS:
            if level > current_percent:
                self.zoom_level = level / 100
                self._update_zoom()
                break

    def zoom_out(self) -> None:
        """Zoom out to the previous zoom level."""
        current_percent = int(self.zoom_level * 100)
        for level in reversed(self.ZOOM_LEVELS):
            if level < current_percent:
                self.zoom_level = level / 100
                self._update_zoom()
                break

    def _update_zoom(self) -> None:
        """Update zoom level for all pages."""
        if self.doc:
            # Remember the current page before re-rendering
            current_page = self.current_page

            # Re-render all pages with new zoom
            self._render_all_pages()

            # Jump back to the page we were on
            self.jump_to_page(current_page)

    def rotate_left(self) -> None:
        """Rotate the view 90 degrees counterclockwise."""
        idx = self.ROTATION_ANGLES.index(self.rotation_angle)
        idx = (idx - 1) % len(self.ROTATION_ANGLES)
        self.rotation_angle = self.ROTATION_ANGLES[idx]
        self._update_rotation()

    def rotate_right(self) -> None:
        """Rotate the view 90 degrees clockwise."""
        idx = self.ROTATION_ANGLES.index(self.rotation_angle)
        idx = (idx + 1) % len(self.ROTATION_ANGLES)
        self.rotation_angle = self.ROTATION_ANGLES[idx]
        self._update_rotation()

    def _update_rotation(self) -> None:
        """Update rotation for all pages."""
        # Update rotation for PyMuPDF rendering
        if self.doc:
            # Remember the current page before re-rendering
            current_page = self.current_page

            # Re-render all pages with new rotation
            self._render_all_pages()

            # Jump back to the page we were on
            self.jump_to_page(current_page)

        # Store rotation in PDF manager for persistence
        if self.pdf_manager and hasattr(self.pdf_manager, "_rotation"):
            self.pdf_manager._rotation = self.rotation_angle

    def next_page(self) -> None:
        """Go to the next page."""
        if self.doc and self.current_page < self.total_pages - 1:
            self.jump_to_page(self.current_page + 1)

    def previous_page(self) -> None:
        """Go to the previous page."""
        if self.doc and self.current_page > 0:
            self.jump_to_page(self.current_page - 1)

    def jump_to_page(self, page_num: int) -> None:
        """Jump to a specific page.

        Args:
            page_num: The page number to jump to (0-indexed)
        """
        if not self.doc or page_num < 0 or page_num >= self.total_pages:
            return

        try:
            # Set flag to avoid triggering scroll handler
            self._programmatic_scroll = True

            # Get the target page widget
            if page_num < len(self.page_container.page_widgets):
                target_widget = self.page_container.page_widgets[page_num]

                # Scroll to the widget's position
                self.scroll_area.ensureWidgetVisible(target_widget, 0, 0)

                # Update current page
                self.current_page = page_num
                self._update_page_indicator()
                self.pageChanged.emit(self.current_page, self.total_pages)

            # Reset flag
            self._programmatic_scroll = False

        except Exception as e:
            logger = get_logger()
            logger.error(f"Error jumping to page {page_num}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._programmatic_scroll = False

    def fit_width(self) -> None:
        """Fit the pages to the width of the viewport."""
        if not self.doc:
            return

        # Get scroll area width (accounting for scrollbar)
        scroll_width = self.scroll_area.viewport().width()
        if self.scroll_area.verticalScrollBar().isVisible():
            scroll_width -= self.scroll_area.verticalScrollBar().width()

        # Add some margin for better visual appearance
        scroll_width -= 40  # 20px margin on each side

        # Get the current page for reference
        page = self.doc[0]  # Use first page as reference

        # Calculate zoom factor to fit width
        page_width = page.rect.width
        new_zoom = scroll_width / page_width

        # Set new zoom level
        self.zoom_level = new_zoom
        self._update_zoom()

    def fit_page(self) -> None:
        """Fit the pages to the height of the viewport."""
        if not self.doc:
            return

        # Get the current page for reference
        page = self.doc[0]  # Use first page as reference

        # Get scroll area dimensions (accounting for scrollbars)
        scroll_width = self.scroll_area.viewport().width()
        scroll_height = self.scroll_area.viewport().height()

        if self.scroll_area.verticalScrollBar().isVisible():
            scroll_width -= self.scroll_area.verticalScrollBar().width()

        # Add some margin for better visual appearance
        scroll_width -= 40  # 20px margin on each side
        scroll_height -= 40  # 20px margin on top and bottom

        # Calculate zoom factors for width and height
        page_width = page.rect.width
        page_height = page.rect.height

        zoom_width = scroll_width / page_width
        zoom_height = scroll_height / page_height

        # Use the smaller zoom factor to ensure the entire page fits
        new_zoom = min(zoom_width, zoom_height) * 0.95  # 95% to add a small margin

        # Set new zoom level
        self.zoom_level = new_zoom
        self._update_zoom()
