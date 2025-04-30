from PyQt6.QtGui import QColor, QFont, QPalette


def apply_mac_style(app):
    """Apply a macOS-inspired style to the application."""
    # Set the Fusion style as the base
    app.setStyle("Fusion")

    # Create a custom palette with lighter colors
    palette = QPalette()

    # Base colors
    window_color = QColor(249, 249, 249)
    text_color = QColor(33, 33, 33)
    accent_color = QColor(0, 122, 255)  # Apple blue

    # Set colors for various UI elements
    palette.setColor(QPalette.ColorRole.Window, window_color)
    palette.setColor(QPalette.ColorRole.WindowText, text_color)
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(242, 242, 242))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
    palette.setColor(QPalette.ColorRole.Text, text_color)
    palette.setColor(QPalette.ColorRole.Button, window_color)
    palette.setColor(QPalette.ColorRole.ButtonText, text_color)
    palette.setColor(QPalette.ColorRole.Link, accent_color)
    palette.setColor(QPalette.ColorRole.Highlight, accent_color)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    # Apply palette
    app.setPalette(palette)

    # Set system font
    app.setFont(QFont("system-ui", 10))

    # Apply stylesheet
    app.setStyleSheet("""
        /* Main window and widgets */
        QMainWindow, QDialog {
            background-color: #f9f9f9;
            border: none;
        }
        
        /* Tab Widget */
        QTabWidget::pane {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            background-color: white;
            top: -1px;
        }
        
        QTabBar::tab {
            background-color: #f0f0f0;
            border: 1px solid #e0e0e0;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
            color: #505050;
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: none;
            color: #000000;
        }
        
        QTabBar::tab:hover:!selected {
            background-color: #e8e8e8;
        }
        
        /* Push Buttons */
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #d1d1d1;
            border-radius: 5px;
            padding: 8px 16px;
            color: #333333;
            min-height: 24px;
        }
        
        QPushButton:hover {
            background-color: #f5f5f5;
            border-color: #b1b1b1;
        }
        
        QPushButton:pressed {
            background-color: #e6e6e6;
        }
        
        QPushButton:disabled {
            background-color: #f9f9f9;
            color: #b1b1b1;
            border-color: #e0e0e0;
        }
        
        QPushButton:focus {
            border: 1px solid #007aff;
            background-color: #f0f7ff;
        }
        
        QPushButton:default {
            background-color: #007aff;
            color: white;
            border: 1px solid #0062cc;
        }
        
        QPushButton:default:hover {
            background-color: #0069d9;
        }
        
        QPushButton:default:pressed {
            background-color: #0062cc;
        }
        
        /* Line Edits */
        QLineEdit {
            border: 1px solid #d1d1d1;
            border-radius: 4px;
            padding: 5px 8px;
            background-color: white;
            selection-background-color: #007aff;
            min-height: 24px;
        }
        
        QLineEdit:focus {
            border: 1px solid #007aff;
        }
        
        QLineEdit:disabled {
            background-color: #f5f5f5;
            color: #999999;
        }
        
        /* Combo Boxes */
        QComboBox {
            border: 1px solid #d1d1d1;
            border-radius: 4px;
            padding: 5px 8px;
            background-color: white;
            min-height: 24px;
        }
        
        QComboBox:focus {
            border: 1px solid #007aff;
        }
        
        QComboBox:hover {
            border-color: #b1b1b1;
        }
        
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: none;
        }
        
        QComboBox::down-arrow {
            width: 14px;
            height: 14px;
        }
        
        QComboBox QAbstractItemView {
            border: 1px solid #d1d1d1;
            selection-background-color: #e6f2ff;
            selection-color: #000000;
            background-color: white;
            outline: 0;
        }
        
        /* Check Boxes */
        QCheckBox {
            spacing: 8px;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #d1d1d1;
            border-radius: 3px;
            background-color: white;
        }
        
        QCheckBox::indicator:checked {
            background-color: #007aff;
            border-color: #007aff;
        }
        
        QCheckBox::indicator:hover {
            border-color: #b1b1b1;
        }
        
        /* Scroll Bars */
        QScrollBar:vertical {
            border: none;
            background-color: #f5f5f5;
            width: 12px;
            margin: 0px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #c1c1c1;
            min-height: 20px;
            border-radius: 6px;
            margin: 2px;
            width: 8px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #a1a1a1;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QScrollBar:horizontal {
            border: none;
            background-color: #f5f5f5;
            height: 12px;
            margin: 0px;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #c1c1c1;
            min-width: 20px;
            border-radius: 6px;
            margin: 2px;
            height: 8px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #a1a1a1;
        }
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        
        /* Frames and Sections */
        QFrame {
            border-radius: 5px;
        }
        
        QFrame[frameShape="4"] {  /* QFrame::Shape::StyledPanel */
            border: 1px solid #e0e0e0;
            background-color: white;
        }
        
        /* Labels */
        QLabel {
            color: #333333;
            border: none;
            background: transparent;
        }
        
        QLabel[heading="true"] {
            font-weight: bold;
            font-size: 13px;
            color: #000000;
            border: none;
            background: transparent;
        }
        
        /* Tool Bars */
        QToolBar {
            background-color: #f9f9f9;
            border: none;
            border-bottom: 1px solid #e0e0e0;
            spacing: 2px;
        }
        
        QToolButton {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 3px;
            margin: 1px;
        }
        
        QToolButton:hover {
            background-color: #f0f0f0;
            border: 1px solid #e0e0e0;
        }
        
        QToolButton:pressed {
            background-color: #e0e0e0;
        }
        
        /* Status Bar */
        QStatusBar {
            background-color: #f9f9f9;
            color: #505050;
            border-top: 1px solid #e0e0e0;
        }
        
        /* Splitter */
        QSplitter::handle {
            background-color: #e0e0e0;
        }
        
        QSplitter::handle:horizontal {
            width: 1px;
        }
        
        QSplitter::handle:vertical {
            height: 1px;
        }
        
        /* Headers */
        QHeaderView::section {
            background-color: #f5f5f5;
            border: none;
            border-right: 1px solid #e0e0e0;
            border-bottom: 1px solid #e0e0e0;
            padding: 5px;
        }
        
        /* Progress Bar */
        QProgressBar {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            background-color: #f5f5f5;
            padding: 1px;
            text-align: center;
        }
        
        QProgressBar::chunk {
            background-color: #007aff;
            border-radius: 3px;
        }
    """)
