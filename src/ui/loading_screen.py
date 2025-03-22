from __future__ import annotations
from typing import Optional, Any
import time
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import (
    Qt,
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
ENABLE_PERF_LOGGING = False  # Set to True only for debugging


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

    # Define color constants - Updated with Mac-inspired colors
    COLOR_PRIMARY = QColor(0, 122, 255)  # Apple blue
    COLOR_SECONDARY = QColor(88, 86, 214)  # Apple purple
    COLOR_TERTIARY = QColor(52, 199, 89)  # Apple green
    COLOR_BG_LIGHT = QColor(255, 255, 255, 245)
    COLOR_BG_DARK = QColor(250, 250, 250, 245)
    COLOR_SHADOW = QColor(0, 0, 0, 20)
    COLOR_BORDER = QColor(229, 229, 234, 100)
    COLOR_TRACK = QColor(229, 229, 234, 150)
    COLOR_TEXT_TITLE = QColor(0, 0, 0)  # Black for title
    COLOR_TEXT_PROGRESS = QColor(128, 128, 128)  # Gray for progress text
    COLOR_BG_TRANSLUCENT = QColor(248, 248, 248, 220)

    # Animation constants
    FADE_IN_MS = 200  # Faster fade-in for better visual experience

    # Performance optimization flags
    ENABLE_PERF_LOGGING = False  # Disabled by default for production

    @log_performance
    def __init__(
        self, parent: Optional[QWidget] = None, app_name: str = "File Organizer"
    ) -> None:
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

        super().__init__(parent)

        if ENABLE_PERF_LOGGING:
            super_time = time.time()
            logger.debug(
                f"__init__ - super().__init__() took {(super_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = super_time

        # Window properties
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Set initial opacity higher so background is visible from start
        self._splash_opacity = 0.8

        if ENABLE_PERF_LOGGING:
            window_time = time.time()
            logger.debug(
                f"__init__ - window properties took {(window_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = window_time

        # Initialize state
        self.app_name = app_name
        self.progress = 0
        self.progress_text = ""
        self._dots = 0
        self.angle = 0
        # Start with higher opacity so background is visible immediately
        self._splash_opacity = 0.9
        self._pulse_radius = 0
        self._pulse_opacity = 0.6

        # Cache for optimized rendering
        self._center_point = None
        self._container_rect = None
        self._shadow_rect = None
        self._cached_bg_gradient = None
        self._cached_pulse_colors = {}
        self._cached_progress_gradient = None

        if ENABLE_PERF_LOGGING:
            state_time = time.time()
            logger.debug(
                f"__init__ - state initialization took {(state_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = state_time

        # Initialize dimensions first
        self._calculate_dimensions()

        if ENABLE_PERF_LOGGING:
            dim_time = time.time()
            logger.debug(
                f"__init__ - _calculate_dimensions() took {(dim_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = dim_time
            
        # Pre-calculate expensive rendering elements
        self._precalculate_rendering_elements()
        
        if ENABLE_PERF_LOGGING:
            precalc_time = time.time()
            logger.debug(
                f"__init__ - _precalculate_rendering_elements() took {(precalc_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = precalc_time

        # Initialize fonts without creating metrics yet
        self._percentage_font = QFont()
        self._percentage_font.setPointSize(int(self.message_font_size * 0.8))

        # Initialize font metrics as None - will create on demand
        self._font_metrics = None
        self._text_height = None

        if ENABLE_PERF_LOGGING:
            font_time = time.time()
            logger.debug(
                f"__init__ - font initialization took {(font_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = font_time

        # Initialize UI and animations
        self._setup_ui()

        if ENABLE_PERF_LOGGING:
            ui_time = time.time()
            logger.debug(
                f"__init__ - _setup_ui() took {(ui_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = ui_time

        self._setup_animations()

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"__init__ - _setup_animations() took {(end_time - phase_start) * 1000:.2f}ms"
            )
            logger.debug(
                f"__init__ - total initialization took {(end_time - total_start) * 1000:.2f}ms"
            )

    @log_performance
    def _calculate_dimensions(self) -> None:
        """Calculate all dimensions and spacing based on screen size and golden ratio principles."""
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

        # Golden ratio for aesthetic proportions
        golden_ratio = (1 + 5**0.5) / 2

        # Get screen dimensions and calculate base unit
        screen_rect = self.screen().geometry()
        self.base_unit = min(screen_rect.width(), screen_rect.height()) / 60

        if ENABLE_PERF_LOGGING:
            screen_time = time.time()
            logger.debug(
                f"_calculate_dimensions - screen dimensions took {(screen_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = screen_time

        # Core dimensions
        self.progress_ring_radius = int(self.base_unit * 8)
        self.padding_vertical = int(self.base_unit * 4)
        self.padding_horizontal = int(self.base_unit * 4 * golden_ratio)
        self.element_spacing = int(self.base_unit * 2)

        # Font sizes
        self.title_font_size = max(int(self.base_unit * 3), 18)
        self.message_font_size = max(int(self.base_unit * 1.5), 12)

        if ENABLE_PERF_LOGGING:
            core_time = time.time()
            logger.debug(
                f"_calculate_dimensions - core dimensions took {(core_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = core_time

        # Container dimensions
        container_width = int(self.progress_ring_radius * 2 * golden_ratio * 2)
        container_height = (
            int(container_width / golden_ratio) + self.padding_vertical * 2
        )
        self.container_width = max(container_width, 300)
        self.container_height = max(container_height, 200)

        # Widget size calculation
        widget_width = self.container_width + (self.padding_horizontal * 2)
        widget_height = self.container_height + (self.padding_vertical * 2)

        if ENABLE_PERF_LOGGING:
            container_time = time.time()
            logger.debug(
                f"_calculate_dimensions - container calculations took {(container_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = container_time

        # Set widget size
        self.setFixedSize(widget_width, widget_height)

        if ENABLE_PERF_LOGGING:
            resize_time = time.time()
            logger.debug(
                f"_calculate_dimensions - setFixedSize took {(resize_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = resize_time

        # Progress bar dimensions
        self.progress_bar_height = int(self.base_unit)
        self.progress_bar_width = int(self.container_width * 0.75)
        self.progress_bar_radius = int(self.progress_bar_height / 2)

        # Define vertical spacing for better element distribution
        self.title_margin_top = int(self.container_height * 0.15)
        self.progress_bar_margin_bottom = int(self.container_height * 0.25)

        # Pulse circle parameters
        self.pulse_max_radius = self.progress_ring_radius * 1.5
        self.pulse_min_radius = self.progress_ring_radius * 1.2

        # Logo dimensions
        self.logo_size = QSize(
            int(self.progress_ring_radius * 0.8), int(self.progress_ring_radius * 0.8)
        )

        if ENABLE_PERF_LOGGING:
            other_time = time.time()
            logger.debug(
                f"_calculate_dimensions - other calculations took {(other_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = other_time

        # Reset caches
        self._container_rect = None
        self._shadow_rect = None
        self._cached_bg_gradient = None

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"_calculate_dimensions - cache reset took {(end_time - phase_start) * 1000:.2f}ms"
            )
            logger.debug(
                f"_calculate_dimensions - total time: {(end_time - total_start) * 1000:.2f}ms"
            )

    def _precalculate_rendering_elements(self) -> None:
        """Pre-calculate expensive rendering elements to avoid first-paint delays"""
        # Create center point
        self._center_point = QPointF(self.rect().center())
        
        # Create container rect
        self._container_rect = QRect(
            int(self._center_point.x() - self.container_width / 2),
            int(self._center_point.y() - self.container_height / 2),
            self.container_width,
            self.container_height,
        )
        
        # Create shadow rect
        shadow_offset = 10
        self._shadow_rect = QRect(
            self._container_rect.x() - shadow_offset // 2,
            self._container_rect.y() - shadow_offset // 2,
            self._container_rect.width() + shadow_offset,
            self._container_rect.height() + shadow_offset,
        )
        
        # Pre-create background gradient
        topLeft = QPointF(self._container_rect.topLeft())
        bottomLeft = QPointF(self._container_rect.bottomLeft())
        self._cached_bg_gradient = QLinearGradient(topLeft, bottomLeft)
        self._cached_bg_gradient.setColorAt(0, self.COLOR_BG_LIGHT)
        self._cached_bg_gradient.setColorAt(1, self.COLOR_BG_DARK)
        
        # Pre-create progress gradient
        bar_left = (self.width() - self.progress_bar_width) / 2
        bar_top = self._container_rect.bottom() - self.progress_bar_margin_bottom
        self._cached_progress_gradient = QLinearGradient(
            QPointF(bar_left, bar_top), QPointF(bar_left + self.progress_bar_width, bar_top)
        )
        self._cached_progress_gradient.setColorAt(0, self.COLOR_PRIMARY)
        self._cached_progress_gradient.setColorAt(1, self.COLOR_SECONDARY)
    
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
            # Recalculate rendering elements after resize
            self._precalculate_rendering_elements()

    def _setup_ui(self) -> None:
        """Set up the UI components using the calculated dimensions."""
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

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

        if ENABLE_PERF_LOGGING:
            layout_time = time.time()
            logger.debug(
                f"_setup_ui - layout creation took {(layout_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = layout_time

        # Create and setup labels
        self._create_labels(main_layout)

        if ENABLE_PERF_LOGGING:
            labels_time = time.time()
            logger.debug(
                f"_setup_ui - _create_labels took {(labels_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = labels_time

        # Set the layout margins to center content properly
        self.setLayout(main_layout)

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"_setup_ui - setLayout took {(end_time - phase_start) * 1000:.2f}ms"
            )
            logger.debug(
                f"_setup_ui - total time: {(end_time - total_start) * 1000:.2f}ms"
            )

    def _create_labels(self, layout) -> None:
        """Create and configure all text labels."""
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

        # Title label
        self.title_label = QLabel(self.app_name)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(self.title_font_size)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet(f"color: {self.COLOR_TEXT_TITLE.name()};")
        layout.addWidget(self.title_label)

        if ENABLE_PERF_LOGGING:
            title_time = time.time()
            logger.debug(
                f"_create_labels - title label creation took {(title_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = title_time

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

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"_create_labels - progress label creation took {(end_time - phase_start) * 1000:.2f}ms"
            )
            logger.debug(
                f"_create_labels - total time: {(end_time - total_start) * 1000:.2f}ms"
            )

    @log_performance
    def _setup_animations(self) -> None:
        """Set up all animations for a dynamic user experience."""
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

        # Skip pre-calculations - we've already done them in _precalculate_rendering_elements
        
        # Create a faster fade-in with higher start opacity for better perceived performance
        self._create_animation(
            b"splash_opacity",
            0.95,  # Start at higher opacity
            1.0,
            self.FADE_IN_MS,
            easing=QEasingCurve.Type.OutCubic,
            loop=False,
        )

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"_setup_animations - fade animation setup took {(end_time - phase_start) * 1000:.2f}ms"
            )
            logger.debug(
                f"_setup_animations - total time: {(end_time - total_start) * 1000:.2f}ms"
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
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

        # Create animation
        animation = QPropertyAnimation(self, property_name, self)
        animation.setDuration(duration)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(easing)

        if ENABLE_PERF_LOGGING:
            setup_time = time.time()
            logger.debug(
                f"_create_animation - animation setup took {(setup_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = setup_time

        # Configure loop
        if loop:
            animation.setLoopCount(-1)  # Infinite loop

        # Start animation
        animation.start()

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"_create_animation - animation start took {(end_time - phase_start) * 1000:.2f}ms"
            )
            logger.debug(
                f"_create_animation - total time: {(end_time - total_start) * 1000:.2f}ms"
            )

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
        total_start_time = time.time() if ENABLE_PERF_LOGGING else 0
        phase_start_time = total_start_time

        # Initialize painter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if ENABLE_PERF_LOGGING:
            init_time = time.time()
            logger.debug(
                f"paintEvent - painter init took {(init_time - phase_start_time) * 1000:.2f}ms"
            )
            phase_start_time = init_time

        # Cache center point for multiple drawing operations
        if self._center_point is None:
            self._center_point = QPointF(self.rect().center())
            if ENABLE_PERF_LOGGING:
                center_time = time.time()
                logger.debug(
                    f"paintEvent - center point calculation took {(center_time - phase_start_time) * 1000:.2f}ms"
                )
                phase_start_time = center_time

        # Apply global opacity for fade-in effect
        painter.setOpacity(self._splash_opacity)

        if ENABLE_PERF_LOGGING:
            bg_time = time.time()
            logger.debug(
                f"paintEvent - opacity setup took {(bg_time - phase_start_time) * 1000:.2f}ms"
            )
            phase_start_time = bg_time

        # Draw container
        self._draw_container(painter)
        if ENABLE_PERF_LOGGING:
            container_time = time.time()
            logger.debug(
                f"paintEvent - container drawing took {(container_time - phase_start_time) * 1000:.2f}ms"
            )
            phase_start_time = container_time

        # Draw progress bar
        self._draw_progress_bar(painter)
        if ENABLE_PERF_LOGGING:
            progress_time = time.time()
            logger.debug(
                f"paintEvent - progress bar drawing took {(progress_time - phase_start_time) * 1000:.2f}ms"
            )
            phase_start_time = progress_time

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"paintEvent - total time: {(end_time - total_start_time) * 1000:.2f}ms"
            )

    # Configuration for optimized rendering
    USE_SIMPLE_SHADOW = True  # Use simpler shadow rendering for better performance

    def _draw_container(self, painter: QPainter) -> None:
        """Draw the container background with subtle shadow."""
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

        # Get center point if not cached
        if not self._center_point:
            self._center_point = QPointF(self.width() / 2, self.height() / 2)
            if ENABLE_PERF_LOGGING:
                center_time = time.time()
                logger.debug(
                    f"_draw_container - center point calculation took {(center_time - phase_start) * 1000:.2f}ms"
                )
                phase_start = center_time

        # Calculate container rect if not cached
        if not self._container_rect:
            self._container_rect = QRect(
                int(self._center_point.x() - self.container_width / 2),
                int(self._center_point.y() - self.container_height / 2),
                self.container_width,
                self.container_height,
            )
            if ENABLE_PERF_LOGGING:
                rect_time = time.time()
                logger.debug(
                    f"_draw_container - container rect calculation took {(rect_time - phase_start) * 1000:.2f}ms"
                )
                phase_start = rect_time

        # Calculate shadow rect if not cached (slightly larger than container)
        if not self._shadow_rect:
            shadow_offset = 10
            self._shadow_rect = QRect(
                self._container_rect.x() - shadow_offset // 2,
                self._container_rect.y() - shadow_offset // 2,
                self._container_rect.width() + shadow_offset,
                self._container_rect.height() + shadow_offset,
            )
            if ENABLE_PERF_LOGGING:
                shadow_time = time.time()
                logger.debug(
                    f"_draw_container - shadow rect calculation took {(shadow_time - phase_start) * 1000:.2f}ms"
                )
                phase_start = shadow_time

        # Draw shadow with optimized rendering
        painter.setPen(Qt.PenStyle.NoPen)
        if self.USE_SIMPLE_SHADOW:
            # Use simpler shadow with better performance
            painter.setBrush(QColor(0, 0, 0, 15))  # Lighter, less expensive shadow
            painter.drawRect(self._shadow_rect)  # Regular rect instead of rounded
        else:
            # Original shadow code
            painter.setBrush(self.COLOR_SHADOW)
            painter.drawRoundedRect(self._shadow_rect, 10, 10)

        if ENABLE_PERF_LOGGING:
            shadow_draw_time = time.time()
            logger.debug(
                f"_draw_container - shadow drawing took {(shadow_draw_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = shadow_draw_time

        # Draw container background
        gradient_created = False
        if not self._cached_bg_gradient:
            # Convert QPoint to QPointF for the gradient
            topLeft = QPointF(self._container_rect.topLeft())
            bottomLeft = QPointF(self._container_rect.bottomLeft())

            self._cached_bg_gradient = QLinearGradient(topLeft, bottomLeft)
            self._cached_bg_gradient.setColorAt(0, self.COLOR_BG_LIGHT)
            self._cached_bg_gradient.setColorAt(1, self.COLOR_BG_DARK)
            gradient_created = True

        painter.setBrush(self._cached_bg_gradient)
        painter.setPen(QPen(self.COLOR_BORDER, 1))
        painter.drawRoundedRect(self._container_rect, 10, 10)

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            if gradient_created:
                logger.debug(
                    f"_draw_container - gradient creation and drawing took {(end_time - phase_start) * 1000:.2f}ms"
                )
            else:
                logger.debug(
                    f"_draw_container - container drawing took {(end_time - phase_start) * 1000:.2f}ms"
                )
            logger.debug(
                f"_draw_container - total time: {(end_time - total_start) * 1000:.2f}ms"
            )

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
        """Draw a MacOS-style progress bar."""
        if ENABLE_PERF_LOGGING:
            total_start = time.time()
            phase_start = total_start

        # Calculate dimensions
        bar_width = self.progress_bar_width
        bar_height = self.progress_bar_height
        bar_left = (self.width() - bar_width) / 2
        bar_top = self._container_rect.bottom() - self.progress_bar_margin_bottom
        progress_width = int(bar_width * (self.progress / 100))

        if ENABLE_PERF_LOGGING:
            calc_time = time.time()
            logger.debug(
                f"_draw_progress_bar - calculations took {(calc_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = calc_time

        # Draw bar background (track)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.COLOR_TRACK)
        painter.drawRoundedRect(
            int(bar_left),
            int(bar_top),
            bar_width,
            bar_height,
            self.progress_bar_radius,
            self.progress_bar_radius,
        )

        if ENABLE_PERF_LOGGING:
            track_time = time.time()
            logger.debug(
                f"_draw_progress_bar - track drawing took {(track_time - phase_start) * 1000:.2f}ms"
            )
            phase_start = track_time

        # Draw progress bar if there is progress
        if progress_width > 0:
            gradient_created = False
            # Create gradient for progress bar if not cached
            if not self._cached_progress_gradient:
                self._cached_progress_gradient = QLinearGradient(
                    QPointF(bar_left, bar_top), QPointF(bar_left + bar_width, bar_top)
                )
                self._cached_progress_gradient.setColorAt(0, self.COLOR_PRIMARY)
                self._cached_progress_gradient.setColorAt(1, self.COLOR_SECONDARY)
                gradient_created = True

                if ENABLE_PERF_LOGGING:
                    gradient_time = time.time()
                    logger.debug(
                        f"_draw_progress_bar - gradient creation took {(gradient_time - phase_start) * 1000:.2f}ms"
                    )
                    phase_start = gradient_time

            painter.setBrush(self._cached_progress_gradient)
            painter.drawRoundedRect(
                int(bar_left),
                int(bar_top),
                progress_width,
                bar_height,
                self.progress_bar_radius,
                self.progress_bar_radius,
            )

            if ENABLE_PERF_LOGGING:
                progress_time = time.time()
                if gradient_created:
                    logger.debug(
                        f"_draw_progress_bar - progress bar drawing with new gradient took {(progress_time - phase_start) * 1000:.2f}ms"
                    )
                else:
                    logger.debug(
                        f"_draw_progress_bar - progress bar drawing with cached gradient took {(progress_time - phase_start) * 1000:.2f}ms"
                    )
                phase_start = progress_time

        # Draw progress text with improved placement
        if self.progress > 0 or self.progress_text:
            self._draw_percentage_text(painter, bar_left, bar_top)
            if ENABLE_PERF_LOGGING:
                text_time = time.time()
                logger.debug(
                    f"_draw_progress_bar - text drawing took {(text_time - phase_start) * 1000:.2f}ms"
                )
                phase_start = text_time

        if ENABLE_PERF_LOGGING:
            end_time = time.time()
            logger.debug(
                f"_draw_progress_bar - total time: {(end_time - total_start) * 1000:.2f}ms"
            )

    def _draw_percentage_text(
        self, painter: QPainter, bar_left: float, bar_top: float
    ) -> None:
        """Draw the percentage text below the progress bar."""
        # Initialize font metrics if not already created
        if self._font_metrics is None:
            if ENABLE_PERF_LOGGING:
                metrics_start = time.time()

            # Create font metrics only when needed
            self._font_metrics = QFontMetrics(self._percentage_font)
            self._text_height = self._font_metrics.height()

            if ENABLE_PERF_LOGGING:
                metrics_time = time.time()
                logger.debug(
                    f"_draw_percentage_text - font metrics initialization took {(metrics_time - metrics_start) * 1000:.2f}ms"
                )

        painter.setPen(QColor(50, 50, 50, 200))
        painter.setFont(self._percentage_font)

        percentage_text = f"{self.progress}%"
        text_width = self._font_metrics.horizontalAdvance(percentage_text)

        # Position text in the center of the bar
        text_x = bar_left + (self.progress_bar_width - text_width) / 2

        # Leave some space between the bar and text
        text_y = bar_top + self.progress_bar_height + self._text_height + 5

        # Ensure text stays within container bounds
        container_bottom = self._container_rect.bottom()
        if text_y + self._text_height > container_bottom:
            text_y = (
                bar_top - self._text_height - 5
            )  # Move text above the bar if no space below

        painter.drawText(QPointF(text_x, text_y), percentage_text)
