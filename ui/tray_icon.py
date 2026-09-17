"""System Tray integration for instant 1-click account switching from Windows taskbar."""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal

from core.config import config
from core.profile_manager import profile_manager
from core.process_manager import process_manager


def create_tray_pixmap(text: str = "C", bg_color: str = "#d97706") -> QPixmap:
    """Dynamically generate a high-DPI crisp system tray icon."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw rounded background
    painter.setBrush(QColor(bg_color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 16, 16)

    # Draw letter
    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI", 30, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()

    return pixmap


class ClaudeTrayIcon(QSystemTrayIcon):
    """System tray icon providing quick-switch menu and status notifications."""

    switch_account_requested = pyqtSignal(str)
    show_window_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setToolTip("Claude Multi-Account Switcher")
        self.setIcon(QIcon(create_tray_pixmap()))
        self.activated.connect(self._on_tray_activated)
        self.update_menu()

    def update_menu(self):
        """Rebuild context menu to reflect current accounts and active state."""
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background-color: #1a1d24; border: 1px solid #33394a; border-radius: 8px; padding: 6px; } "
            "QMenu::item { padding: 8px 22px; color: #f3f4f6; border-radius: 4px; font-size: 13px; } "
            "QMenu::item:selected { background-color: #2d3343; color: #f59e0b; } "
            "QMenu::separator { height: 1px; background: #2e3545; margin: 4px 8px; }"
        )

        accounts_data = config.load_accounts()
        accounts_map = accounts_data.get("accounts", {})
        active_id = accounts_data.get("active_account_id")

        # Header item
        title_action = menu.addAction("✦ Claude Multi-Account")
        title_action.setEnabled(False)
        menu.addSeparator()

        # Accounts List
        for acc_id, acc in accounts_map.items():
            is_active = (acc_id == active_id)
            prefix = "● " if is_active else "○ "
            action = menu.addAction(f"{prefix}{acc.get('name')}")
            if is_active:
                font = action.font()
                font.setBold(True)
                action.setFont(font)
            action.triggered.connect(lambda _, a_id=acc_id: self.switch_account_requested.emit(a_id))

        menu.addSeparator()

        # Dashboard & Controls
        open_action = menu.addAction("Open Dashboard")
        open_action.triggered.connect(self.show_window_requested.emit)

        restart_action = menu.addAction("Restart Claude Desktop")
        restart_action.triggered.connect(process_manager.restart_claude)

        menu.addSeparator()

        exit_action = menu.addAction("Exit Claude Switcher")
        exit_action.triggered.connect(self._exit_app)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()

    def _exit_app(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
