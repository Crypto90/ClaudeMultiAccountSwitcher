"""Guided wizard dialog for safely adding and signing into new Claude accounts."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


AVATAR_PALETTE = [
    ("#8b5cf6", "Violet"),
    ("#06b6d4", "Cyan"),
    ("#10b981", "Emerald"),
    ("#f43f5e", "Rose"),
    ("#3b82f6", "Blue"),
    ("#ea580c", "Orange"),
]


class AddAccountDialog(QDialog):
    """Dialog guiding user through the account addition process with zero risk to current login."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Claude Account")
        self.setFixedSize(520, 440)
        self.selected_color = AVATAR_PALETTE[0][0]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        # Title
        title_label = QLabel("Add New Claude Account")
        title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        layout.addWidget(title_label)

        # Safety Assurance Box
        safety_box = QFrame()
        safety_box.setStyleSheet(
            "background-color: #064e3b; border: 1px solid #059669; border-radius: 10px; padding: 12px;"
        )
        safety_layout = QVBoxLayout(safety_box)
        safety_layout.setSpacing(4)

        shield_title = QLabel("🛡️ Safe & Protected")
        shield_title.setStyleSheet("color: #34d399; font-weight: 700; font-size: 13px;")
        safety_layout.addWidget(shield_title)

        shield_desc = QLabel(
            "Your existing signed-in account is backed up. Claude Desktop will open in "
            "fresh sign-in mode for your new account. Once you log in, Claude Switcher "
            "will automatically capture and register your new profile."
        )
        shield_desc.setWordWrap(True)
        shield_desc.setStyleSheet("color: #d1fae5; font-size: 12px;")
        safety_layout.addWidget(shield_desc)

        layout.addWidget(safety_box)

        # Account Name Input
        name_layout = QVBoxLayout()
        name_layout.setSpacing(6)
        name_lbl = QLabel("Account Name / Label:")
        name_lbl.setStyleSheet("font-weight: 600; color: #f3f4f6;")
        name_layout.addWidget(name_lbl)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Work Account, Client Org, Personal Pro...")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # Color Selector
        color_layout = QVBoxLayout()
        color_layout.setSpacing(6)
        color_lbl = QLabel("Avatar Accent Color:")
        color_lbl.setStyleSheet("font-weight: 600; color: #f3f4f6;")
        color_layout.addWidget(color_lbl)

        palette_row = QHBoxLayout()
        palette_row.setSpacing(12)
        self.color_group = QButtonGroup(self)

        for idx, (hex_code, label) in enumerate(AVATAR_PALETTE):
            btn = QRadioButton(label)
            btn.setStyleSheet(f"QRadioButton {{ color: #e5e7eb; }} QRadioButton::indicator:checked {{ background-color: {hex_code}; border-color: #ffffff; }}")
            if idx == 0:
                btn.setChecked(True)
            self.color_group.addButton(btn, idx)
            palette_row.addWidget(btn)

        color_layout.addLayout(palette_row)
        layout.addLayout(color_layout)

        # Share MCP Configuration Checkbox
        self.mcp_checkbox = QCheckBox("Share custom MCP server configurations across accounts")
        self.mcp_checkbox.setChecked(True)
        layout.addWidget(self.mcp_checkbox)

        layout.addStretch()

        # Action Buttons
        btns_layout = QHBoxLayout()
        btns_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(cancel_btn)

        self.start_btn = QPushButton("Start Setup & Open Claude")
        self.start_btn.setProperty("class", "primary-btn")
        self.start_btn.clicked.connect(self._on_start)
        btns_layout.addWidget(self.start_btn)

        layout.addLayout(btns_layout)

    def _on_start(self):
        name = self.name_input.text().strip()
        if not name:
            self.name_input.setFocus()
            return

        idx = self.color_group.checkedId()
        if 0 <= idx < len(AVATAR_PALETTE):
            self.selected_color = AVATAR_PALETTE[idx][0]

        self.accept()

    def get_account_data(self):
        """Returns (account_name, avatar_color, share_mcp)."""
        return (
            self.name_input.text().strip() or "Second Account",
            self.selected_color,
            self.mcp_checkbox.isChecked()
        )
