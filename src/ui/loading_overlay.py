from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtCore import Qt, QTimer, QRectF

class LoadingOverlay(QWidget):
    """
    A semi-transparent overlay widget with a simple loading spinner animation.
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        self._timer.setInterval(50)  # Update ~20 times per second

        # Make the widget transparent for mouse events initially
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Ensure the widget is transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Hide by default
        self.hide()

    def paintEvent(self, event):
        """Handles painting the overlay background and spinner."""
        if not self.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Semi-transparent background
        painter.fillRect(self.rect(), QColor(255, 255, 255, 180))

        # Spinner properties
        center = self.rect().center()
        radius = min(self.width(), self.height()) // 6 # Adjust size as needed
        pen_width = max(2, radius // 8)

        painter.translate(center)
        painter.rotate(self._angle)

        pen = QPen(QColor(50, 50, 50, 220)) # Dark gray spinner
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw a simple arc or line for the spinner
        # Draw an arc segment
        rect = QRectF(-radius, -radius, 2 * radius, 2 * radius)
        start_angle = 0 * 16 # Angle in 1/16ths of a degree
        span_angle = 120 * 16 # Length of the arc
        painter.drawArc(rect, start_angle, span_angle)

        # Alternatively, draw a rotating line:
        # painter.drawLine(0, radius // 2, 0, radius)

        painter.end()

    def _update_animation(self):
        """Updates the rotation angle and triggers a repaint."""
        self._angle = (self._angle + 10) % 360
        self.update() # Trigger paintEvent

    def showEvent(self, event):
        """Starts the animation timer when the widget is shown."""
        # Make the widget block mouse events when visible
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.raise_() # Ensure it's on top of siblings
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        """Stops the animation timer when the widget is hidden."""
        # Make the widget transparent for mouse events again when hidden
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        """Ensures the overlay covers the parent widget."""
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        super().resizeEvent(event)

# Example usage (for testing standalone)
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QPushButton

    app = QApplication(sys.argv)

    window = QMainWindow()
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)

    # Create a container widget that the overlay will cover
    container = QWidget()
    container.setFixedSize(300, 200)
    container.setStyleSheet("background-color: lightblue; border: 1px solid blue;")
    container_layout = QVBoxLayout(container)
    container_layout.addWidget(QLabel("Content Below Overlay"))
    container_layout.addWidget(QPushButton("Button Below"))

    layout.addWidget(container)

    # Create and show the overlay
    overlay = LoadingOverlay(container)

    # Buttons to control the overlay
    show_button = QPushButton("Show Overlay")
    hide_button = QPushButton("Hide Overlay")
    show_button.clicked.connect(overlay.show)
    hide_button.clicked.connect(overlay.hide)

    layout.addWidget(show_button)
    layout.addWidget(hide_button)

    window.setCentralWidget(central_widget)
    window.resize(400, 300)
    window.show()

    sys.exit(app.exec())