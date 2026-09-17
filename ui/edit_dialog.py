"""Dialog to edit account profile name, avatar color, and remove accounts."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QRadioButton, QButtonGroup, QMessageBox,
    QColorDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush, QFont


COLOR_PRESETS = [
    ("#d97706", "Terracotta"),
    ("#8b5cf6", "Violet"),
    ("#10b981", "Emerald"),
    ("#06b6d4", "Cyan"),
    ("#f43f5e", "Rose"),
    ("#3b82f6", "Blue"),
    ("#eab308", "Amber"),
    ("#64748b", "Slate")
]


class LiveAvatarPreview(QLabel):
    """Circular avatar that updates in real time as name and color change."""

    def __init__(self, text: str, bg_color: str, parent=None):
        super().__init__(parent)
        self.text = (text[0] if text else "C").upper()
        self.bg_color = bg_color
        self.setFixedSize(64, 64)

    def update_avatar(self, name: str, color_hex: str):
        self.text = (name[0] if name else "C").upper()
        self.bg_color = color_hex
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw outer glowing halo ring
        halo_color = QColor(self.bg_color)
        halo_color.setAlpha(60)
        painter.setPen(QPen(halo_color, 2))
        painter.setBrush(QBrush(QColor(16, 20, 30)))
        painter.drawEllipse(1, 1, 62, 62)

        # Draw inner vibrant circle
        inner_color = QColor(self.bg_color)
        painter.setPen(QPen(inner_color.lighter(135), 1.5))
        painter.setBrush(QBrush(inner_color))
        painter.drawEllipse(7, 7, 50, 50)

        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)


class EditAccountDialog(QDialog):
    """Modal dialog allowing users to rename, recolor, or delete an account."""

    account_deleted = pyqtSignal(str)  # account_id

    def __init__(self, account_data: dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.account_data = account_data
        self.account_id = account_data["id"]
        self.is_active = is_active
        self.current_color = account_data.get("avatar_color", "#d97706")

        self.setWindowTitle(f"Edit Profile - {account_data.get('name')}")
        self.setFixedSize(480, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Title
        title_lbl = QLabel("✦ Edit Account Profile")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title_lbl)

        # Avatar Preview Card
        preview_frame = QFrame()
        preview_frame.setProperty("class", "card-frame")
        preview_layout = QHBoxLayout(preview_frame)
        preview_layout.setContentsMargins(16, 14, 16, 14)
        preview_layout.setSpacing(16)

        self.avatar_preview = LiveAvatarPreview(
            self.account_data.get("name", "C"), self.current_color
        )
        preview_layout.addWidget(self.avatar_preview)

        preview_info = QVBoxLayout()
        preview_info.setSpacing(4)
        preview_title = QLabel("Avatar Preview")
        preview_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #f3f4f6;")
        preview_info.addWidget(preview_title)

        uuid_val = self.account_data.get("account_uuid") or "Pending UUID"
        short_uuid = f"UUID: {uuid_val[:8]}..." if len(uuid_val) > 8 else f"UUID: {uuid_val}"
        preview_sub = QLabel(f"{short_uuid}\nChanges update instantly in cards & system tray.")
        preview_sub.setStyleSheet("color: #9ca3af; font-size: 11px;")
        preview_info.addWidget(preview_sub)

        preview_layout.addLayout(preview_info, stretch=1)
        layout.addWidget(preview_frame)

        # Name Input
        name_layout = QVBoxLayout()
        name_layout.setSpacing(6)
        name_lbl = QLabel("Account Name:")
        name_lbl.setStyleSheet("font-weight: 600; color: #f3f4f6;")
        name_layout.addWidget(name_lbl)

        self.name_input = QLineEdit(self.account_data.get("name", ""))
        self.name_input.textChanged.connect(self._on_input_changed)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # Color Selection
        color_layout = QVBoxLayout()
        color_layout.setSpacing(8)
        color_lbl = QLabel("Choose Avatar Color:")
        color_lbl.setStyleSheet("font-weight: 600; color: #f3f4f6;")
        color_layout.addWidget(color_lbl)

        palette_layout = QHBoxLayout()
        palette_layout.setSpacing(8)
        self.color_group = QButtonGroup(self)

        matched_idx = -1
        for idx, (hex_code, label) in enumerate(COLOR_PRESETS):
            btn = QRadioButton()
            btn.setToolTip(label)
            btn.setStyleSheet(
                f"QRadioButton::indicator {{ width: 22px; height: 22px; border-radius: 11px; background-color: {hex_code}; border: 2px solid transparent; }} "
                f"QRadioButton::indicator:checked {{ border: 2px solid #ffffff; }} "
                f"QRadioButton::indicator:hover {{ border: 2px solid #9ca3af; }}"
            )
            if hex_code.lower() == self.current_color.lower():
                btn.setChecked(True)
                matched_idx = idx
            self.color_group.addButton(btn, idx)
            palette_layout.addWidget(btn)

        if matched_idx == -1 and self.color_group.buttons():
            self.color_group.buttons()[0].setChecked(True)

        self.color_group.idToggled.connect(self._on_preset_color_toggled)
        palette_layout.addStretch()

        # Custom Color Button
        custom_color_btn = QPushButton("Custom...")
        custom_color_btn.setFixedHeight(28)
        custom_color_btn.clicked.connect(self._pick_custom_color)
        palette_layout.addWidget(custom_color_btn)

        color_layout.addLayout(palette_layout)
        layout.addLayout(color_layout)

        layout.addStretch()

        # Danger Zone: Remove Account
        danger_layout = QHBoxLayout()
        self.delete_btn = QPushButton("Remove This Account")
        self.delete_btn.setProperty("class", "danger-btn")
        self.delete_btn.clicked.connect(self._on_delete_clicked)

        if self.is_active:
            self.delete_btn.setEnabled(False)
            self.delete_btn.setToolTip("Cannot remove the currently active account. Switch to another account first.")

        danger_layout.addWidget(self.delete_btn)
        danger_layout.addStretch()

        # Action Buttons
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        danger_layout.addWidget(cancel_btn)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setProperty("class", "primary-btn")
        self.save_btn.clicked.connect(self.accept)
        danger_layout.addWidget(self.save_btn)

        layout.addLayout(danger_layout)

    def _on_input_changed(self):
        name = self.name_input.text().strip()
        self.avatar_preview.update_avatar(name, self.current_color)

    def _on_preset_color_toggled(self, btn_id: int, checked: bool):
        if checked and 0 <= btn_id < len(COLOR_PRESETS):
            self.current_color = COLOR_PRESETS[btn_id][0]
            self._on_input_changed()

    def _pick_custom_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, "Pick Avatar Color")
        if color.isValid():
            self.current_color = color.name()
            # Uncheck presets
            if self.color_group.checkedButton():
                self.color_group.setExclusive(False)
                self.color_group.checkedButton().setChecked(False)
                self.color_group.setExclusive(True)
            self._on_input_changed()

    def _on_delete_clicked(self):
        name = self.account_data.get("name", "this account")
        confirm = QMessageBox.warning(
            self, "Confirm Account Removal",
            f"Are you sure you want to remove profile '{name}' from Claude Switcher?\n\n"
            "This will remove the local profile from the switcher.\n"
            "(Your original baseline backup is always preserved).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.account_deleted.emit(self.account_id)
            self.reject()

    def get_updated_data(self):
        """Returns (new_name, new_color)."""
        name = self.name_input.text().strip() or self.account_data.get("name", "Claude")
        return name, self.current_color
