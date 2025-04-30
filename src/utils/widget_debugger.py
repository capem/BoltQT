from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QApplication, QToolBar

from .logger import get_logger


class WidgetDebugger(QObject):
    """Event filter for debugging widgets by clicking on them.
    
    This class provides a convenient way to identify UI elements by clicking on them.
    When enabled, clicking any widget will:
    1. Print detailed information about the widget in the console
    2. Highlight the widget with a red border
    3. Show all siblings if the parent is a toolbar
    
    Usage:
        # Enable globally
        WidgetDebugger.enable()
        
        # Disable globally
        WidgetDebugger.disable()
        
        # Toggle state
        WidgetDebugger.toggle()
    """
    
    _instance = None
    _enabled = False
    
    @classmethod
    def instance(cls):
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = WidgetDebugger()
        return cls._instance
    
    @classmethod
    def enable(cls):
        """Enable widget debugging application-wide."""
        if not cls._enabled:
            app = QApplication.instance()
            if app:
                app.installEventFilter(cls.instance())
                cls._enabled = True
                logger = get_logger()
                logger.info("Widget debugging enabled. Click on elements to identify them.")

    @classmethod
    def disable(cls):
        """Disable widget debugging application-wide."""
        if cls._enabled:
            app = QApplication.instance()
            if app:
                app.removeEventFilter(cls.instance())
                cls._enabled = False
                logger = get_logger()
                logger.info("Widget debugging disabled.")

    @classmethod
    def toggle(cls):
        """Toggle debugging on/off."""
        if cls._enabled:
            cls.disable()
        else:
            cls.enable()
    
    @classmethod
    def is_enabled(cls):
        """Check if debugging is currently enabled."""
        return cls._enabled
    
    def __init__(self):
        """Initialize the widget debugger."""
        super().__init__()
        self.tracked_widgets = set()
        self.highlight_widget = None
        self.original_stylesheet = ""
    
    def eventFilter(self, obj, event):
        """Print information about the widget when clicked and highlight it."""
        if event.type() == QEvent.Type.MouseButtonPress:
            if obj not in self.tracked_widgets and hasattr(obj, "setStyleSheet"):
                self.tracked_widgets.add(obj)

                # Get logger
                logger = get_logger()

                # Log widget information
                logger.info("=== WIDGET CLICKED ===")
                logger.info(f"Widget Type: {type(obj).__name__}")
                logger.info(f"Object Name: {obj.objectName()}")

                # Get widget position and size
                geo = obj.geometry()
                logger.info(f"Geometry: x={geo.x()}, y={geo.y()}, w={geo.width()}, h={geo.height()}")

                # Get parent information
                if obj.parent():
                    logger.info(f"Parent: {type(obj.parent()).__name__} ({obj.parent().objectName()})")

                    # If parent is QToolBar, log all its children
                    if isinstance(obj.parent(), QToolBar):
                        logger.info("Siblings in toolbar:")
                        for i in range(obj.parent().layout().count()):
                            item = obj.parent().layout().itemAt(i)
                            if item and item.widget():
                                child = item.widget()
                                logger.info(f"  Child {i}: {type(child).__name__} ({child.objectName()})")

                # Get stylesheet
                if obj.styleSheet():
                    logger.info(f"StyleSheet: {obj.styleSheet()}")

                # If it's a QToolButton or similar, log text
                if hasattr(obj, "text") and callable(obj.text):
                    logger.info(f"Text: {obj.text()}")

                # Remove highlight from previous widget
                if self.highlight_widget and self.highlight_widget != obj:
                    self.highlight_widget.setStyleSheet(self.original_stylesheet)
                
                # Highlight current widget
                self.highlight_widget = obj
                self.original_stylesheet = obj.styleSheet()
                obj.setStyleSheet(f"{self.original_stylesheet}; border: 2px solid red !important;")
                
                # Reset tracking after 5 seconds to allow re-clicking
                QTimer.singleShot(5000, lambda: self._reset_tracking(obj))
        
        # Always return False to allow the event to propagate
        return False
    
    def _reset_tracking(self, obj):
        """Reset tracking for a widget and remove highlighting."""
        if obj in self.tracked_widgets:
            self.tracked_widgets.remove(obj)
            
            # Remove highlighting if this is the currently highlighted widget
            if obj == self.highlight_widget:
                obj.setStyleSheet(self.original_stylesheet)
                self.highlight_widget = None


# Create global key bindings to enable/disable debugging
def setup_global_debug_shortcut(parent):
    """Set up a global shortcut (Ctrl+Shift+D) to toggle widget debugging.
    
    Args:
        parent: The widget to attach the shortcut to.
    """
    logger = get_logger()
    logger.debug("Setting up widget debugger shortcut (Ctrl+Shift+D)")

    # Create the debug action
    debug_action = QAction("Toggle Widget Debugging", parent)
    debug_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
    debug_action.triggered.connect(WidgetDebugger.toggle)
    parent.addAction(debug_action)