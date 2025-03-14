from __future__ import annotations
from typing import Optional, Any, Tuple
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize, 
                          pyqtProperty, QParallelAnimationGroup, QSequentialAnimationGroup, QPointF,
                          QRect)
from PyQt6.QtGui import (QPainter, QColor, QPainterPath, QLinearGradient, QPen, 
                         QFont, QFontMetrics, QBrush, QRadialGradient)
import math

class EnhancedLoadingScreen(QWidget):
    """
    A visually engaging loading screen with dynamic layout calculations, responsive design,
    and optimized perceived performance.
    """
    
    def __init__(self, parent: Optional[QWidget] = None, app_name: str = "File Organizer") -> None:
        super().__init__(parent)
        
        # Window properties
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Initialize state
        self.app_name = app_name
        self.progress = 0  # 0-100
        self.progress_text = ""
        self.tips = ["Organizing files...", "Analyzing content...", "Preparing your workspace..."]
        self.current_tip_index = 0
        self._dots = 0
        self.angle = 0
        self._splash_opacity = 0.0
        
        # Initialize animation-related attributes
        self._pulse_radius = self.pulse_min_radius if hasattr(self, 'pulse_min_radius') else 0
        self._pulse_opacity = 0.6
        
        # Initialize dynamic layout calculations
        self._calculate_dimensions()
        
        # Set up the UI components
        self._setup_ui()
        
        # Set up animations
        self._setup_animations()
    
    def _calculate_dimensions(self) -> None:
        """
        Calculate all dimensions and spacing based on screen size and golden ratio principles.
        This provides a mathematically pleasing layout that scales across different devices.
        """
        # Get screen dimensions
        screen_rect = self.screen().geometry()
        screen_width = screen_rect.width()
        screen_height = screen_rect.height()
        
        # Calculate optimal base unit (1/60th of the smaller screen dimension)
        # This ensures the base unit scales appropriately regardless of screen orientation
        self.base_unit = min(screen_width, screen_height) / 60
        
        # Calculate golden ratio (approximately 1.618)
        golden_ratio = (1 + 5 ** 0.5) / 2
        
        # Apply golden ratio for aesthetic dimensions
        self.progress_ring_radius = int(self.base_unit * 8)
        self.padding_vertical = int(self.base_unit * 4)
        self.padding_horizontal = int(self.base_unit * 4 * golden_ratio)
        
        # Define spacing using the base unit for consistency
        self.element_spacing = int(self.base_unit * 2)
        
        # Define font sizes relative to base unit
        self.title_font_size = max(int(self.base_unit * 3), 18)
        self.message_font_size = max(int(self.base_unit * 1.5), 12)
        
        # Set container size using golden ratio
        container_width = int(self.progress_ring_radius * 2 * golden_ratio * 2)
        container_height = int(container_width / golden_ratio)
        
        # Ensure minimum size
        min_width = 300
        min_height = 200
        self.container_width = max(container_width, min_width)
        self.container_height = max(container_height, min_height)
        
        # Set widget size (container + padding)
        self.setFixedSize(
            self.container_width + (self.padding_horizontal * 2),
            self.container_height + (self.padding_vertical * 2)
        )
        
        # Calculate center point
        self.center_x = self.width() / 2
        self.center_y = self.height() / 2
        
        # Calculate progress bar dimensions
        self.progress_bar_height = int(self.base_unit * 1)
        self.progress_bar_width = int(self.container_width * 0.75)
        self.progress_bar_radius = int(self.progress_bar_height / 2)
        
        # Calculate pulsing circle parameters
        self.pulse_max_radius = self.progress_ring_radius * 1.5
        self.pulse_min_radius = self.progress_ring_radius * 1.2
        
        # Calculate logo dimensions (if used)
        self.logo_size = QSize(
            int(self.progress_ring_radius * 0.8), 
            int(self.progress_ring_radius * 0.8)
        )
    
    def _setup_ui(self) -> None:
        """Set up the UI components using the calculated dimensions."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            self.padding_horizontal, 
            self.padding_vertical, 
            self.padding_horizontal, 
            self.padding_vertical
        )
        main_layout.setSpacing(self.element_spacing)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title label
        self.title_label = QLabel(self.app_name)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(self.title_font_size)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet(f"color: #2c3e50;")
        main_layout.addWidget(self.title_label)
        
        # Spacer
        main_layout.addSpacing(self.element_spacing)
        
        # Progress text label
        self.progress_label = QLabel("Loading...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_font = QFont()
        msg_font.setPointSize(self.message_font_size)
        self.progress_label.setFont(msg_font)
        self.progress_label.setStyleSheet("color: #7f8c8d;")
        main_layout.addWidget(self.progress_label)
        
        # Tip label for user engagement
        self.tip_label = QLabel(self.tips[0])
        self.tip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tip_label.setFont(msg_font)
        self.tip_label.setStyleSheet("color: #95a5a6; font-style: italic;")
        main_layout.addWidget(self.tip_label)
        
        # Apply fade effect to tip label
        self.tip_opacity = QGraphicsOpacityEffect(self.tip_label)
        self.tip_opacity.setOpacity(0.8)
        self.tip_label.setGraphicsEffect(self.tip_opacity)
    
    def _setup_animations(self) -> None:
        """Set up all animations for a dynamic user experience."""
        # Spinner rotation timer
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._update_spinner)
        self.spinner_timer.start(30)  # Smoother 30ms update
        
        # Pulsing circle animation
        self.pulse_animation = QPropertyAnimation(self, b"pulseRadius", self)
        self.pulse_animation.setDuration(1800)
        self.pulse_animation.setStartValue(self.pulse_min_radius)
        self.pulse_animation.setEndValue(self.pulse_max_radius)
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.pulse_animation.setLoopCount(-1)  # Infinite
        
        # Pulsing opacity animation
        self.pulse_opacity_animation = QPropertyAnimation(self, b"pulseOpacity", self)
        self.pulse_opacity_animation.setDuration(1800)
        self.pulse_opacity_animation.setStartValue(0.6)
        self.pulse_opacity_animation.setEndValue(0.0)
        self.pulse_opacity_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.pulse_opacity_animation.setLoopCount(-1)  # Infinite
        
        # Dot animation
        self.dot_animation = QPropertyAnimation(self, b"dots", self)
        self.dot_animation.setDuration(1000)
        self.dot_animation.setStartValue(0)
        self.dot_animation.setEndValue(3)
        self.dot_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.dot_animation.setLoopCount(-1)  # Infinite
        
        # Tip rotation timer
        self.tip_timer = QTimer(self)
        self.tip_timer.timeout.connect(self._rotate_tip)
        self.tip_timer.start(5000)  # Change tip every 5 seconds
        
        # Start animations
        self.pulse_animation.start()
        self.pulse_opacity_animation.start()
        self.dot_animation.start()
        
        # Fade-in animation for initial appearance
        self.fade_in = QPropertyAnimation(self, b"splash_opacity", self)
        self.fade_in.setDuration(400)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_in.start()
    
    def _update_spinner(self) -> None:
        """Update spinner animation angle."""
        self.angle = (self.angle + 3) % 360
        self.update()
    
    def _rotate_tip(self) -> None:
        """Rotate through tips with a fade transition."""
        # Fade out current tip
        fade_out = QPropertyAnimation(self.tip_opacity, b"opacity", self)
        fade_out.setDuration(300)
        fade_out.setStartValue(0.8)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Fade in new tip
        fade_in = QPropertyAnimation(self.tip_opacity, b"opacity", self)
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(0.8)
        fade_in.setEasingCurve(QEasingCurve.Type.InQuad)
        
        # Create sequential animation
        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(fade_out)
        sequence.addPause(100)  # Brief pause to show the change
        sequence.addAnimation(fade_in)
        
        # Connect to property update
        sequence.finished.connect(self._update_tip_text)
        sequence.start()
    
    def _update_tip_text(self) -> None:
        """Update the tip text after fade out."""
        self.current_tip_index = (self.current_tip_index + 1) % len(self.tips)
        self.tip_label.setText(self.tips[self.current_tip_index])
    
    # Property getters and setters for animations
    @pyqtProperty(float)
    def splash_opacity(self) -> float:
        return self._splash_opacity
    
    @splash_opacity.setter
    def splash_opacity(self, opacity: float) -> None:
        self._splash_opacity = opacity
        self.update()
    
    @pyqtProperty(int)
    def dots(self) -> int:
        return self._dots
    
    @dots.setter
    def dots(self, value: int) -> None:
        self._dots = value
        self._update_dots()
    
    @pyqtProperty(float)
    def pulseRadius(self) -> float:
        return self._pulse_radius
    
    @pulseRadius.setter
    def pulseRadius(self, radius: float) -> None:
        self._pulse_radius = radius
        self.update()
    
    @pyqtProperty(float)
    def pulseOpacity(self) -> float:
        return self._pulse_opacity
    
    @pulseOpacity.setter
    def pulseOpacity(self, opacity: float) -> None:
        self._pulse_opacity = opacity
        self.update()
    
    def _update_dots(self) -> None:
        """Update the loading text with animated dots."""
        dots_text = "." * (self._dots)
        self.progress_label.setText(f"{self.progress_text}{dots_text}")
    
    def set_progress(self, value: int, text: str = "") -> None:
        """
        Update the progress value and text.
        
        Args:
            value: Progress value (0-100)
            text: Optional text to display instead of percentage
        """
        self.progress = max(0, min(100, value))  # Clamp between 0-100
        self.progress_text = text if text else f"Loading {self.progress}%"
        self._update_dots()
        self.update()
    
    def add_tip(self, tip: str) -> None:
        """Add a new tip to the rotation."""
        if tip not in self.tips:
            self.tips.append(tip)
    
    def paintEvent(self, event: Any) -> None:
        """Custom paint event to render all visual elements."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Apply global opacity for fade-in effect
        painter.setOpacity(self._splash_opacity)
        
        # Draw translucent background
        bg_color = QColor(245, 245, 245, 200)
        painter.fillRect(self.rect(), bg_color)
        
        # Draw container with subtle shadow effect
        self._draw_container(painter)
        
        # Draw pulsing background circle (for perceived activity)
        if hasattr(self, "_pulse_radius") and hasattr(self, "_pulse_opacity"):
            self._draw_pulse_circle(painter)
        
        # Draw progress ring
        self._draw_progress_ring(painter)
        
        # Draw progress bar
        self._draw_progress_bar(painter)
    
    def _draw_container(self, painter: QPainter) -> None:
        """Draw the main container with shadow effect."""
        # Calculate container rect
        container_rect = self.rect().adjusted(
            self.padding_horizontal, 
            self.padding_vertical, 
            -self.padding_horizontal, 
            -self.padding_vertical
        )
        
        # Draw subtle shadow (blurred rectangle)
        shadow_color = QColor(0, 0, 0, 30)
        shadow_rect = container_rect.adjusted(2, 2, 2, 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_color)
        painter.drawRoundedRect(shadow_rect, self.base_unit, self.base_unit)
        
        # Draw container background
        bg_gradient = QLinearGradient(0, container_rect.top(), 0, container_rect.bottom())
        bg_gradient.setColorAt(0, QColor(255, 255, 255, 240))
        bg_gradient.setColorAt(1, QColor(248, 248, 248, 240))
        
        painter.setBrush(bg_gradient)
        painter.setPen(QPen(QColor(220, 220, 220, 100), 1))
        painter.drawRoundedRect(container_rect, self.base_unit, self.base_unit)
    
    def _draw_pulse_circle(self, painter: QPainter) -> None:
        """Draw the pulsing background circle for visual engagement."""
        center = QPointF(self.rect().center())
        
        # Create radial gradient for pulsing effect
        gradient = QRadialGradient(center, self._pulse_radius)
        pulse_color = QColor(52, 152, 219, int(self._pulse_opacity * 255))
        gradient.setColorAt(0, pulse_color)
        gradient.setColorAt(0.7, QColor(pulse_color.red(), pulse_color.green(), pulse_color.blue(), int(pulse_color.alpha() * 0.5)))
        gradient.setColorAt(1, QColor(pulse_color.red(), pulse_color.green(), pulse_color.blue(), 0))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, self._pulse_radius, self._pulse_radius)
    
    def _draw_progress_ring(self, painter: QPainter) -> None:
        """Draw the circular progress indicator with rotating segments."""
        center = self.rect().center()
        
        # Save painter state
        painter.save()
        painter.translate(center)
        
        # Calculate arc dimensions
        outer_radius = self.progress_ring_radius
        inner_radius = int(outer_radius * 0.75)
        segment_width = (outer_radius - inner_radius) / 2
        
        # Define colors
        primary_color = QColor(52, 152, 219)  # Blue
        secondary_color = QColor(46, 204, 113)  # Green
        tertiary_color = QColor(155, 89, 182)  # Purple
        
        # Draw 12 segments with varying opacity
        for i in range(12):
            # Rotate to segment position
            segment_angle = i * 30
            adjusted_angle = (segment_angle + self.angle) % 360
            
            # Calculate opacity based on position (brightest at top)
            opacity = 0.3 + 0.7 * (1 - abs((adjusted_angle % 360) - 180) / 180)
            
            # Determine segment color
            color_index = i % 3
            if color_index == 0:
                color = primary_color
            elif color_index == 1:
                color = secondary_color
            else:
                color = tertiary_color
            
            # Apply opacity
            color.setAlphaF(opacity)
            
            # Draw segment
            painter.rotate(30)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            
            # Create segment path
            segment_path = QPainterPath()
            segment_path.arcMoveTo(-outer_radius, -outer_radius, outer_radius * 2, outer_radius * 2, -15)
            segment_path.arcTo(-outer_radius, -outer_radius, outer_radius * 2, outer_radius * 2, -15, 30)
            segment_path.arcTo(-inner_radius, -inner_radius, inner_radius * 2, inner_radius * 2, 15, -30)
            segment_path.closeSubpath()
            
            # Draw the segment
            painter.drawPath(segment_path)
        
        painter.restore()
    
    def _draw_progress_bar(self, painter: QPainter) -> None:
        """Draw the horizontal progress bar below the spinner."""
        if self.progress <= 0:
            return  # Don't draw if no progress
            
        # Calculate progress bar position
        center = self.rect().center()
        bar_top = center.y() + self.progress_ring_radius + self.element_spacing * 2
        bar_left = center.x() - (self.progress_bar_width / 2)
        
        # Draw background track
        track_rect = QRect(
            int(bar_left),
            int(bar_top),
            self.progress_bar_width,
            self.progress_bar_height
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(220, 220, 220, 150))
        painter.drawRoundedRect(track_rect, self.progress_bar_radius, self.progress_bar_radius)
        
        # Draw filled portion
        if self.progress > 0:
            fill_width = int(self.progress_bar_width * (self.progress / 100))
            fill_rect = QRect(
                int(bar_left),
                int(bar_top),
                fill_width,
                self.progress_bar_height
            )
            
            # Create gradient for filled portion
            gradient = QLinearGradient(
                fill_rect.left(), fill_rect.top(),
                fill_rect.right(), fill_rect.top()
            )
            gradient.setColorAt(0, QColor(52, 152, 219))  # Blue
            gradient.setColorAt(1, QColor(46, 204, 113))  # Green
            
            painter.setBrush(gradient)
            painter.drawRoundedRect(fill_rect, self.progress_bar_radius, self.progress_bar_radius)
        
        # Draw percentage text if progress is significant
        if self.progress > 5:
            painter.setPen(QColor(50, 50, 50, 200))
            percentage_font = QFont()
            percentage_font.setPointSize(int(self.message_font_size * 0.8))
            painter.setFont(percentage_font)
            
            percentage_text = f"{self.progress}%"
            metrics = QFontMetrics(percentage_font)
            text_width = metrics.horizontalAdvance(percentage_text)
            text_height = metrics.height()
            
            # Position text in the center of the bar
            text_x = bar_left + (self.progress_bar_width - text_width) / 2
            text_y = bar_top + self.progress_bar_height + text_height
            
            painter.drawText(QPointF(text_x, text_y), percentage_text)

# Example of how to use the enhanced loading screen
class LoadingScreenDemo:
    @staticmethod
    def create_and_show_loading_screen(parent=None, app_name="File Organizer") -> EnhancedLoadingScreen:
        """Create and show a loading screen with a simulated loading process."""
        loading_screen = EnhancedLoadingScreen(parent, app_name)
        
        # Center on screen
        screen_geometry = loading_screen.screen().geometry()
        x = (screen_geometry.width() - loading_screen.width()) // 2
        y = (screen_geometry.height() - loading_screen.height()) // 2
        loading_screen.move(x, y)
        
        # Show the loading screen
        loading_screen.show()
        
        # Set up a timer for simulated progress updates
        progress_timer = QTimer(loading_screen)
        progress = 0
        
        def update_progress():
            nonlocal progress
            progress += 1
            if progress <= 100:
                loading_screen.set_progress(progress)
            else:
                progress_timer.stop()
                # Close loading screen or transition to main app here
        
        progress_timer.timeout.connect(update_progress)
        progress_timer.start(50)  # Update every 50ms
        
        return loading_screen