"""Safety, backup, and restore management dialog."""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.config import config
from core.profile_manager import profile_manager


class BackupDialog(QDialog):
    """Safety and backup center for restoring snapshots or creating manual backups."""

    restored = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Safety & Backups Center")
        self.setFixedSize(540, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("✦ Safety & Session Backups")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #ffffff;")
        layout.addWidget(title)

        desc = QLabel(
            "Claude Switcher creates protected snapshots so you never lose your active "
            "Claude logins, subscriptions, or authentication tokens."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(desc)

        # Baseline Snapshot Card
        baseline_frame = QFrame()
        baseline_frame.setStyleSheet(
            "background-color: rgba(6, 78, 59, 0.25); border: 1.5px solid rgba(16, 185, 129, 0.5); border-radius: 14px; padding: 16px;"
        )
        base_layout = QVBoxLayout(baseline_frame)
        base_layout.setSpacing(6)

        header_row = QHBoxLayout()
        base_icon = QLabel("🛡️ Original Baseline Session")
        base_icon.setStyleSheet("font-size: 14px; font-weight: 700; color: #34d399;")
        header_row.addWidget(base_icon)

        status_tag = QLabel("IMMUTABLE")
        status_tag.setStyleSheet(
            "background-color: #064e3b; color: #6ee7b7; border: 1px solid #059669; border-radius: 8px; "
            "padding: 3px 10px; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;"
        )
        header_row.addWidget(status_tag)
        header_row.addStretch()
        base_layout.addLayout(header_row)

        manifest_file = config.initial_backup_dir / "backup_manifest.json"
        created_str = "Not yet captured"
        uuid_str = "Unknown"
        if manifest_file.exists():
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                created_str = data.get("created_at", "")[:19].replace("T", " ")
                uuid_str = data.get("account_uuid") or "Primary Session"
            except Exception:
                pass

        details_lbl = QLabel(f"Captured: {created_str}\nOriginal Account UUID: {uuid_str}")
        details_lbl.setStyleSheet("color: #a7f3d0; font-size: 12px; line-height: 1.4;")
        base_layout.addWidget(details_lbl)

        restore_btn = QPushButton("Restore This Original Baseline Session")
        restore_btn.setProperty("class", "danger-btn")
        restore_btn.clicked.connect(self._on_restore_baseline)
        base_layout.addWidget(restore_btn)

        layout.addWidget(baseline_frame)

        # Manual Snapshot Action
        snap_frame = QFrame()
        snap_frame.setProperty("class", "card-frame")
        snap_layout = QHBoxLayout(snap_frame)
        snap_layout.setContentsMargins(14, 12, 14, 12)

        snap_info = QVBoxLayout()
        snap_title = QLabel("Create Snapshot Now")
        snap_title.setStyleSheet("font-weight: 600; color: #f3f4f6;")
        snap_info.addWidget(snap_title)

        snap_sub = QLabel("Back up the current active state to an on-demand restore point.")
        snap_sub.setStyleSheet("color: #9ca3af; font-size: 11px;")
        snap_info.addWidget(snap_sub)
        snap_layout.addLayout(snap_info, stretch=1)

        create_snap_btn = QPushButton("Create Snapshot")
        create_snap_btn.clicked.connect(self._create_snapshot)
        snap_layout.addWidget(create_snap_btn)

        layout.addWidget(snap_frame)
        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _on_restore_baseline(self):
        confirm = QMessageBox.warning(
            self,
            "Confirm Baseline Restore",
            "Are you sure you want to restore the original baseline login?\n\n"
            "Claude Desktop will close for 1 second and re-open with your original session.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                profile_manager.restore_initial_backup()
                QMessageBox.information(
                    self, "Restoration Complete",
                    "Original baseline session restored successfully. Claude Desktop is now running your original login."
                )
                self.restored.emit()
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Restore Failed", f"Could not restore session: {e}")

    def _create_snapshot(self):
        try:
            profile_manager.save_current_profile()
            QMessageBox.information(self, "Snapshot Created", "Active profile snapshot saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save snapshot: {e}")
