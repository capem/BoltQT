from PyQt6.QtWidgets import QTabWidget, QTabBar, QStylePainter, QStyleOptionTab, QStyle
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QFont


class MacTabBar(QTabBar):
    """
    Custom TabBar with macOS-inspired styling
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        # Use system font
        self.setFont(QFont("system-ui", 10))
        # Add spacing between tabs
        self.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
            }
        """)

    def paintEvent(self, event):
        """
        Custom paint event to style tabs in a more macOS-like way
        """
        painter = QStylePainter(self)
        option = QStyleOptionTab()

        for index in range(self.count()):
            self.initStyleOption(option, index)

            # If tab is selected, make it visually stand out
            if self.currentIndex() == index:
                option.state |= QStyle.StateFlag.State_Selected

                # Create custom underline for selected tab
                tab_rect = self.tabRect(index)
                underline_rect = QRect(
                    tab_rect.left() + 2, tab_rect.bottom() - 2, tab_rect.width() - 4, 2
                )

                # Draw the main tab
                painter.drawControl(QStyle.ControlElement.CE_TabBarTab, option)

                # Draw custom underline for selected tab
                painter.save()
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.GlobalColor.blue)
                painter.drawRect(underline_rect)
                painter.restore()
            else:
                # Draw normal tab
                painter.drawControl(QStyle.ControlElement.CE_TabBarTab, option)


class MacTabWidget(QTabWidget):
    """
    TabWidget with macOS-inspired styling
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set custom tab bar
        self.setTabBar(MacTabBar(self))

        # Set tab position to North (top)
        self.setTabPosition(QTabWidget.TabPosition.North)

        # Set document mode for cleaner appearance
        self.setDocumentMode(True)

        # Set styling
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
                top: -1px;
            }
            
            QTabWidget::tab-bar {
                alignment: center;
            }
        """)
