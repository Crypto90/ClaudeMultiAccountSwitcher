"""Account card widget displaying account details, active status, and switch actions."""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QMenu
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont


class AvatarWidget(QLabel):
    """Circular avatar displaying the account's initial letter."""

    def __init__(self, text: str, bg_color: str = "#d97706", parent=None):
        super().__init__(parent)
        self.text = (text[0] if text else "C").upper()
        self.bg_color = bg_color
        self.setFixedSize(48, 48)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw circle
        color = QColor(self.bg_color)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 44, 44)

        # Draw letter
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)


class AccountCard(QFrame):
    """Card widget representing a single Claude account profile."""

    switch_requested = pyqtSignal(str)     # account_id
    rename_requested = pyqtSignal(str)     # account_id
    delete_requested = pyqtSignal(str)     # account_id
    shortcut_requested = pyqtSignal(str)   # account_id

    def __init__(self, account_data: dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.account_data = account_data
        self.account_id = account_data["id"]
        self.is_active = is_active

        self._setup_ui()

    def _setup_ui(self):
        # Set card styling
        if self.is_active:
            self.setProperty("class", "card-frame card-frame-active")
        else:
            self.setProperty("class", "card-frame")

        self.setFixedHeight(110)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(16)

        # Avatar
        avatar_color = self.account_data.get("avatar_color", "#d97706")
        self.avatar = AvatarWidget(self.account_data.get("name", "Claude"), bg_color=avatar_color)
        main_layout.addWidget(self.avatar)

        # Account Details Layout
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)
        details_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Top row: Name + Active Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        name_label = QLabel(self.account_data.get("name", "Unnamed Account"))
        name_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        top_row.addWidget(name_label)

        if self.is_active:
            active_badge = QLabel("ACTIVE NOW")
            active_badge.setProperty("class", "badge-active")
            active_badge.setStyleSheet(
                "background-color: #064e3b; color: #34d399; border: 1px solid #059669; "
                "border-radius: 9px; padding: 2px 8px; font-size: 10px; font-weight: 800;"
            )
            top_row.addWidget(active_badge)

        top_row.addStretch()
        details_layout.addLayout(top_row)

        # Subtitle row: UUID + Last Active
        uuid_val = self.account_data.get("account_uuid") or "No active UUID"
        short_uuid = f"UUID: {uuid_val[:8]}..." if uuid_val and len(uuid_val) > 8 else f"UUID: {uuid_val}"
        last_active = self.account_data.get("last_active", "Recently")[:10]

        sub_label = QLabel(f"{short_uuid}  •  Last active: {last_active}")
        sub_label.setStyleSheet("font-size: 12px; color: #9ca3af;")
        details_layout.addWidget(sub_label)

        main_layout.addLayout(details_layout, stretch=1)

        # Right Action Buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        if not self.is_active:
            switch_btn = QPushButton("Switch To This Account")
            switch_btn.setProperty("class", "primary-btn")
            switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            switch_btn.clicked.connect(lambda: self.switch_requested.emit(self.account_id))
            actions_layout.addWidget(switch_btn)
        else:
            current_pill = QLabel("Current Profile")
            current_pill.setStyleSheet(
                "color: #f59e0b; font-weight: 600; font-size: 12px; padding: 6px 12px; "
                "background-color: #272115; border: 1px solid #78350f; border-radius: 8px;"
            )
            actions_layout.addWidget(current_pill)

        # More Actions Menu button
        menu_btn = QPushButton("•••")
        menu_btn.setFixedWidth(38)
        menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_btn.clicked.connect(self._show_context_menu)
        actions_layout.addWidget(menu_btn)

        main_layout.addLayout(actions_layout)

    def _show_context_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1a1d24; border: 1px solid #33394a; border-radius: 8px; padding: 4px; } "
            "QMenu::item { padding: 8px 20px; color: #f3f4f6; border-radius: 4px; } "
            "QMenu::item:selected { background-color: #2d3343; color: #f59e0b; }"
        )

        rename_action = menu.addAction("Rename Account")
        shortcut_action = menu.addAction("Create Desktop Shortcut")
        menu.addSeparator()

        delete_action = menu.addAction("Delete Account Profile")
        if self.is_active or self.account_data.get("is_primary"):
            delete_action.setEnabled(False)

        action = menu.exec(self.mapToGlobal(self.rect().bottomRight()))
        if action == rename_action:
            self.rename_requested.emit(self.account_id)
        elif action == shortcut_action:
            self.shortcut_requested.emit(self.account_id)
        elif action == delete_action:
            self.delete_requested.emit(self.account_id)
