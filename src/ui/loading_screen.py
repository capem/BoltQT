from __future__ import annotations
from typing import Optional, Any
import time
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QSize,
    pyqtProperty,
    QPointF,
    QRect,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QLinearGradient,
    QPen,
    QFont,
    QFontMetrics,
    QRadialGradient,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("LoadingScreen")

# Performance settings
ENABLE_PERF_LOGGING = True  # Set to True only for debugging


def log_performance(func):
    """Decorator to log the execution time of methods."""

    def wrapper(*args, **kwargs):
        if not ENABLE_PERF_LOGGING:
            return func(*args, **kwargs)

        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        logger.debug(f"{func.__name__} took {(end_time - start_time) * 1000:.2f}ms")
        return result

    return wrapper


class EnhancedLoadingScreen(QWidget):
    """
    A visually engaging loading screen with dynamic layout calculations, responsive design,
    and optimized perceived performance.
    """

    # Define color constants
    COLOR_PRIMARY = QColor(52, 152, 219)  # Blue
    COLOR_SECONDARY = QColor(46, 204, 113)  # Green
    COLOR_TERTIARY = QColor(155, 89, 182)  # Purple
    COLOR_BG_LIGHT = QColor(255, 255, 255, 240)
    COLOR_BG_DARK = QColor(248, 248, 248, 240)
    COLOR_SHADOW = QColor(0, 0, 0, 30)
    COLOR_BORDER = QColor(220, 220, 220, 100)
    COLOR_TRACK = QColor(220, 220, 220, 150)
    COLOR_TEXT_TITLE = QColor(44, 62, 80)  # #2c3e50
    COLOR_TEXT_PROGRESS = QColor(127, 140, 141)  # #7f8c8d
    COLOR_BG_TRANSLUCENT = QColor(245, 245, 245, 200)

    # Animation constants - optimized intervals
    SPINNER_UPDATE_MS = 50  # Reduced update frequency (30ms -> 50ms)
    PULSE_ANIMATION_MS = 2000  # Aligned with common animation intervals
    DOT_ANIMATION_MS = 1000
    FADE_IN_MS = 400

    # Performance optimization flags
    ENABLE_PERF_LOGGING = False  # Disabled by default for production

    @log_performance
    def __init__(
        self, parent: Optional[QWidget] = None, app_name: str = "File Organizer"
    ) -> None:
        super().__init__(parent)

        # Window properties
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Initialize state
        self.app_name = app_name
        self.progress = 0
        self.progress_text = ""
        self._dots = 0
        self.angle = 0
        self._splash_opacity = 0.0
        self._pulse_radius = 0
        self._pulse_opacity = 0.6

        # Cache for optimized rendering
        self._center_point = None
        self._container_rect = None
        self._shadow_rect = None
        self._cached_bg_gradient = None
        self._cached_pulse_colors = {}
        self._cached_progress_gradient = None
        
        # Initialize dimensions first
        self._calculate_dimensions()
        
        # Cache fonts and metrics now that dimensions are calculated
        self._percentage_font = QFont()
        self._percentage_font.setPointSize(int(self.message_font_size * 0.8))
        self._font_metrics = QFontMetrics(self._percentage_font)
        self._text_height = self._font_metrics.height()

        # Initialize UI and animations
        self._setup_ui()
        self._setup_animations()

    @log_performance
    def _calculate_dimensions(self) -> None:
        """Calculate all dimensions and spacing based on screen size and golden ratio principles."""
        # Golden ratio for aesthetic proportions
        golden_ratio = (1 + 5**0.5) / 2

        # Get screen dimensions and calculate base unit
        screen_rect = self.screen().geometry()
        self.base_unit = min(screen_rect.width(), screen_rect.height()) / 60

        # Core dimensions
        self.progress_ring_radius = int(self.base_unit * 8)
        self.padding_vertical = int(self.base_unit * 4)
        self.padding_horizontal = int(self.base_unit * 4 * golden_ratio)
        self.element_spacing = int(self.base_unit * 2)

        # Font sizes
        self.title_font_size = max(int(self.base_unit * 3), 18)
        self.message_font_size = max(int(self.base_unit * 1.5), 12)

        # Container dimensions
        container_width = int(self.progress_ring_radius * 2 * golden_ratio * 2)
        container_height = int(container_width / golden_ratio)
        self.container_width = max(container_width, 300)
        self.container_height = max(container_height, 200)

        # Widget size
        self.setFixedSize(
            self.container_width + (self.padding_horizontal * 2),
            self.container_height + (self.padding_vertical * 2),
        )

        # Progress bar dimensions
        self.progress_bar_height = int(self.base_unit)
        self.progress_bar_width = int(self.container_width * 0.75)
        self.progress_bar_radius = int(self.progress_bar_height / 2)

        # Pulse circle parameters
        self.pulse_max_radius = self.progress_ring_radius * 1.5
        self.pulse_min_radius = self.progress_ring_radius * 1.2

        # Logo dimensions (if used)
        self.logo_size = QSize(
            int(self.progress_ring_radius * 0.8), int(self.progress_ring_radius * 0.8)
        )

        # Precalculate and cache common values for rendering
        self._container_rect = None
        self._shadow_rect = None
        self._cached_bg_gradient = None

    def resizeEvent(self, event) -> None:
        """Handle resize event to recalculate cached values."""
        super().resizeEvent(event)
        if event.size() != event.oldSize():  # Only reset if size actually changed
            self._center_point = None
            self._container_rect = None
            self._shadow_rect = None
            self._cached_bg_gradient = None
            # Keep pulse colors cache as it's opacity-based, not size-based
            self._cached_progress_gradient = None

    def _setup_ui(self) -> None:
        """Set up the UI components using the calculated dimensions."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            self.padding_horizontal,
            self.padding_vertical,
            self.padding_horizontal,
            self.padding_vertical,
        )
        main_layout.setSpacing(self.element_spacing)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create and setup labels
        self._create_labels(main_layout)

    def _create_labels(self, layout) -> None:
        """Create and configure all text labels."""
        # Title label
        self.title_label = QLabel(self.app_name)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(self.title_font_size)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet(f"color: {self.COLOR_TEXT_TITLE.name()};")
        layout.addWidget(self.title_label)

        # Spacer
        layout.addSpacing(self.element_spacing)

        # Progress text label
        self.progress_label = QLabel("Loading...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_font = QFont()
        msg_font.setPointSize(self.message_font_size)
        self.progress_label.setFont(msg_font)
        self.progress_label.setStyleSheet(f"color: {self.COLOR_TEXT_PROGRESS.name()};")
        layout.addWidget(self.progress_label)

    @log_performance
    def _setup_animations(self) -> None:
        """Set up all animations for a dynamic user experience."""
        # Spinner rotation timer
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._update_spinner)

        # Create all animations
        self._create_animation(
            b"splash_opacity",
            0.0,
            1.0,
            self.FADE_IN_MS,
            easing=QEasingCurve.Type.OutCubic,
            loop=False,
        )

    def _create_animation(
        self,
        property_name: bytes,
        start_value: float,
        end_value: float,
        duration: int,
        easing=QEasingCurve.Type.InOutQuad,
        loop=True,
    ) -> None:
        """Helper method to create and start an animation."""
        animation = QPropertyAnimation(self, property_name, self)
        animation.setDuration(duration)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(easing)
        if loop:
            animation.setLoopCount(-1)  # Infinite loop
        animation.start()

    def _update_spinner(self) -> None:
        """Update spinner animation angle."""
        self.angle = (self.angle + 3) % 360
        self.update()

    # Property getters and setters for animations
    @pyqtProperty(float)
    def splash_opacity(self) -> float:
        return self._splash_opacity

    @splash_opacity.setter
    def splash_opacity(self, opacity: float) -> None:
        self._splash_opacity = opacity
        self.update()

    def _update_dots(self) -> None:
        """Update the loading text with animated dots."""
        dots_text = "." * self._dots
        self.progress_label.setText(f"{self.progress_text}{dots_text}")

    def set_progress(self, value: int, text: str = "") -> None:
        """Update the progress value and text."""
        self.progress = max(0, min(100, value))  # Clamp between 0-100
        self.progress_text = text if text else f"Loading {self.progress}%"
        self._update_dots()
        self.update()

    @log_performance
    def paintEvent(self, event: Any) -> None:
        """Custom paint event to render all visual elements."""
        start_time = time.time() if ENABLE_PERF_LOGGING else 0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Cache center point for multiple drawing operations
        if self._center_point is None:
            self._center_point = QPointF(self.rect().center())

        # Apply global opacity for fade-in effect
        painter.setOpacity(self._splash_opacity)

        # Draw translucent background
        painter.fillRect(self.rect(), self.COLOR_BG_TRANSLUCENT)

        # Batch draw operations with minimal state changes
        self._draw_container(painter)
        self._draw_progress_bar(painter)

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(f"paintEvent took {(end_time - start_time) * 1000:.2f}ms")
        logger.debug("paintEvent - end")

    def _draw_container(self, painter: QPainter) -> None:
        """Draw the main container with shadow effect."""
        # Cache container rect calculations
        if self._container_rect is None:
            self._container_rect = self.rect().adjusted(
                self.padding_horizontal,
                self.padding_vertical,
                -self.padding_horizontal,
                -self.padding_vertical,
            )
            self._shadow_rect = self._container_rect.adjusted(2, 2, 2, 2)

        # Draw subtle shadow - simple and fast
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.COLOR_SHADOW)
        painter.drawRoundedRect(self._shadow_rect, self.base_unit, self.base_unit)

        # Cache and reuse gradient
        if self._cached_bg_gradient is None:
            self._cached_bg_gradient = QLinearGradient(
                0, self._container_rect.top(), 0, self._container_rect.bottom()
            )
            self._cached_bg_gradient.setColorAt(0, self.COLOR_BG_LIGHT)
            self._cached_bg_gradient.setColorAt(1, self.COLOR_BG_DARK)

        # Draw container background
        painter.setBrush(self._cached_bg_gradient)
        painter.setPen(QPen(self.COLOR_BORDER, 1))
        painter.drawRoundedRect(self._container_rect, self.base_unit, self.base_unit)

    def _draw_pulse_circle(self, painter: QPainter) -> None:
        """Draw the pulsing background circle for visual engagement."""
        # Skip if opacity is effectively zero
        if self._pulse_opacity < 0.01:
            return

        # Use cached center point
        center = self._center_point

        # Round opacity to reduce cache entries (0.01 precision is sufficient)
        opacity_key = round(self._pulse_opacity * 100) / 100

        # Get or create cached colors
        if opacity_key not in self._cached_pulse_colors:
            pulse_color = QColor(self.COLOR_PRIMARY)
            pulse_color.setAlphaF(opacity_key)

            # Create gradient with fewer color stops
            gradient = QRadialGradient(center, self._pulse_radius)
            gradient.setColorAt(0, pulse_color)
            gradient.setColorAt(
                1, QColor(pulse_color.red(), pulse_color.green(), pulse_color.blue(), 0)
            )

            self._cached_pulse_colors[opacity_key] = gradient

        # Use cached gradient directly
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._cached_pulse_colors[opacity_key])
        painter.drawEllipse(center, self._pulse_radius, self._pulse_radius)

    def _draw_progress_bar(self, painter: QPainter) -> None:
        """Draw the horizontal progress bar below the spinner."""
        if self.progress <= 0:
            return

        # Use cached center point and calculate positions once
        center = self._center_point
        bar_top = int(center.y() + self.progress_ring_radius + self.element_spacing * 2)
        bar_left = int(center.x() - (self.progress_bar_width / 2))

        # Draw background track
        track_rect = QRect(
            bar_left, bar_top, self.progress_bar_width, self.progress_bar_height
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.COLOR_TRACK)
        painter.drawRoundedRect(
            track_rect, self.progress_bar_radius, self.progress_bar_radius
        )

        # Draw progress fill if we have progress
        if self.progress > 0:
            fill_width = int(self.progress_bar_width * (self.progress / 100))

            # Create or update cached gradient if needed
            if self._cached_progress_gradient is None:
                self._cached_progress_gradient = QLinearGradient(
                    0, 0, self.progress_bar_width, 0
                )
                self._cached_progress_gradient.setColorAt(0, self.COLOR_PRIMARY)
                self._cached_progress_gradient.setColorAt(1, self.COLOR_SECONDARY)

            fill_rect = QRect(bar_left, bar_top, fill_width, self.progress_bar_height)
            painter.setBrush(self._cached_progress_gradient)
            painter.drawRoundedRect(
                fill_rect, self.progress_bar_radius, self.progress_bar_radius
            )

            self._draw_percentage_text(painter, float(bar_left), float(bar_top))

    def _draw_percentage_text(
        self, painter: QPainter, bar_left: float, bar_top: float
    ) -> None:
        """Draw the percentage text below the progress bar."""
        painter.setPen(QColor(50, 50, 50, 200))
        painter.setFont(self._percentage_font)

        percentage_text = f"{self.progress}%"
        text_width = self._font_metrics.horizontalAdvance(percentage_text)

        # Position text in the center of the bar
        text_x = bar_left + (self.progress_bar_width - text_width) / 2
        text_y = bar_top + self.progress_bar_height + self._text_height

        painter.drawText(QPointF(text_x, text_y), percentage_text)
