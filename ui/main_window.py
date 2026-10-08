"""Main Dashboard window for Claude Multi-Account Switcher."""

import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QScrollArea, QFrame, QMessageBox,
    QInputDialog, QCheckBox, QDialog, QComboBox, QRadioButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QCursor

from core.config import config
from core.detector import detector
from core.process_manager import process_manager
from core.profile_manager import profile_manager
from core.session_manager import session_manager
from ui.account_card import AccountCard
from ui.session_hub import SessionHubWidget
from ui.add_dialog import AddAccountDialog
from ui.edit_dialog import EditAccountDialog
from ui.backup_dialog import BackupDialog
from ui.tray_icon import ClaudeTrayIcon, create_tray_pixmap
from ui.worker import (
    SwitchAccountWorker, RestartClaudeWorker, CreateAccountWorker, StatusMonitorThread
)


class SwitchPromptDialog(QDialog):
    """Dialog allowing users to select one or multiple in-progress sessions to move or copy over when switching accounts."""

    def __init__(self, target_account_name: str, available_sessions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Switch to {target_account_name}")
        self.setFixedSize(600, 540)
        self.target_account_name = target_account_name
        self.available_sessions = available_sessions
        self.session_checkboxes = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(f"Switching to {self.target_account_name}")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        layout.addWidget(title)

        desc = QLabel(
            f"Select any in-progress or rate-limited sessions to transfer to {self.target_account_name}:"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(desc)

        # Quick selector toolbar
        quick_bar = QHBoxLayout()
        quick_bar.setSpacing(8)

        select_none_btn = QPushButton("Select None")
        select_none_btn.setFixedHeight(28)
        select_none_btn.clicked.connect(self._select_none)
        quick_bar.addWidget(select_none_btn)

        select_recent_btn = QPushButton("Select Most Recent")
        select_recent_btn.setFixedHeight(28)
        select_recent_btn.clicked.connect(self._select_recent)
        quick_bar.addWidget(select_recent_btn)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setFixedHeight(28)
        select_all_btn.clicked.connect(self._select_all)
        quick_bar.addWidget(select_all_btn)

        quick_bar.addStretch()

        self.count_badge = QLabel("0 sessions selected")
        self.count_badge.setStyleSheet("color: #f59e0b; font-weight: 600; font-size: 12px;")
        quick_bar.addWidget(self.count_badge)

        layout.addLayout(quick_bar)

        # Scrollable container for sessions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; background: #0c0f16; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.items_layout = QVBoxLayout(container)
        self.items_layout.setContentsMargins(8, 8, 8, 8)
        self.items_layout.setSpacing(6)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for sess in self.available_sessions:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: #11141e; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 6px; } "
                "QFrame:hover { background-color: #181d2a; border-color: rgba(245, 158, 11, 0.3); }"
            )
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(8, 6, 8, 6)
            c_layout.setSpacing(12)

            cb = QCheckBox()
            cb.stateChanged.connect(self._update_count)
            c_layout.addWidget(cb)
            self.session_checkboxes.append((cb, sess["session_id"]))

            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            t_lbl = QLabel(sess["title"])
            t_lbl.setStyleSheet("font-weight: 700; color: #f3f4f6; font-size: 13px;")
            info_layout.addWidget(t_lbl)

            sub_lbl = QLabel(f"Project: {sess['project_name']}  •  Turns: {sess['turns']}  •  Active: {sess['last_activity_str']}")
            sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
            info_layout.addWidget(sub_lbl)

            c_layout.addLayout(info_layout, stretch=1)
            self.items_layout.addWidget(card)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Mode Selector: Move (Default in all cases) vs Copy
        mode_frame = QFrame()
        mode_frame.setStyleSheet("QFrame { background: #0f121a; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; }")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(12, 8, 12, 8)
        mode_layout.setSpacing(16)

        mode_lbl = QLabel("Action:")
        mode_lbl.setStyleSheet("font-weight: 700; color: #f3f4f6; font-size: 12px;")
        mode_layout.addWidget(mode_lbl)

        self.move_radio = QRadioButton("Move sessions (recommended - remove from current account)")
        self.move_radio.setChecked(True)  # Default option is MOVE in all cases
        self.move_radio.toggled.connect(self._update_count)
        mode_layout.addWidget(self.move_radio)

        self.copy_radio = QRadioButton("Copy sessions (keep in both)")
        self.copy_radio.toggled.connect(self._update_count)
        mode_layout.addWidget(self.copy_radio)

        mode_layout.addStretch()
        layout.addWidget(mode_frame)

        # Bottom Actions
        btns = QHBoxLayout()
        btns.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        self.switch_btn = QPushButton("Switch Account")
        self.switch_btn.setProperty("class", "primary-btn")
        self.switch_btn.clicked.connect(self.accept)
        btns.addWidget(self.switch_btn)

        layout.addLayout(btns)
        self._update_count()

    def is_move_mode(self) -> bool:
        return self.move_radio.isChecked()

    def _update_count(self):
        selected_count = len(self.get_selected_session_ids())
        self.count_badge.setText(f"{selected_count} session(s) selected")
        verb = "Move" if self.is_move_mode() else "Copy"
        if selected_count > 0:
            self.switch_btn.setText(f"Switch & {verb} ({selected_count})")
        else:
            self.switch_btn.setText("Switch (Keep Separate)")

    def _select_all(self):
        for cb, _ in self.session_checkboxes:
            cb.setChecked(True)

    def _select_none(self):
        for cb, _ in self.session_checkboxes:
            cb.setChecked(False)

    def _select_recent(self):
        self._select_none()
        if self.session_checkboxes:
            self.session_checkboxes[0][0].setChecked(True)

    def get_selected_session_ids(self) -> list:
        return [sid for cb, sid in self.session_checkboxes if cb and cb.isChecked()]


class MainWindow(QMainWindow):
    """Master application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Multi-Account Switcher")
        self.resize(840, 640)
        self.setWindowIcon(QIcon(create_tray_pixmap()))

        # Safety initial check on startup
        profile_manager.ensure_initial_backup()

        # System tray setup
        self.tray_icon = ClaudeTrayIcon(self)
        self.tray_icon.switch_account_requested.connect(self._handle_switch_account)
        self.tray_icon.show_window_requested.connect(self._toggle_window_visibility)
        self.tray_icon.show()

        self._setup_ui()

        # Non-blocking background status monitor thread (zero CPU on GUI thread)
        self.status_monitor = StatusMonitorThread(self)
        self.status_monitor.status_updated.connect(self._update_claude_status_from_worker)
        self.status_monitor.start()

        # Pending login watcher timer
        self.pending_watcher = QTimer(self)
        self.pending_watcher.timeout.connect(self._check_pending_logins)

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # Top Bar: Brand Title + Subtitle + Live Status Pill + Actions
        top_bar = QHBoxLayout()
        top_bar.setSpacing(16)

        # Branding Block
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(2)

        title_lbl = QLabel("✦ CLAUDE SWITCHER")
        title_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #f59e0b; letter-spacing: 0.5px;"
        )
        brand_layout.addWidget(title_lbl)

        subtitle_lbl = QLabel("Multi-Account & Session Continuity Engine")
        subtitle_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #a78bfa;"
        )
        brand_layout.addWidget(subtitle_lbl)

        top_bar.addLayout(brand_layout)

        # Live Claude Status Pill
        self.status_pill = QLabel("● Checking Claude...")
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_pill.setMinimumWidth(165)
        self.status_pill.setStyleSheet(
            "background-color: #171b26; color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.1); "
            "padding: 5px 12px; border-radius: 12px; font-size: 11px; font-weight: 700;"
        )
        top_bar.addWidget(self.status_pill)
        top_bar.addStretch()

        # Action Buttons
        self.restart_btn = QPushButton("↻ Restart Claude")
        self.restart_btn.setToolTip("Safely terminate and restart Claude Desktop")
        self.restart_btn.clicked.connect(self._on_restart_claude)
        top_bar.addWidget(self.restart_btn)

        self.backups_btn = QPushButton("🛡️ Safety & Backups")
        self.backups_btn.setToolTip("View immutable baseline backup and manage restore points")
        self.backups_btn.clicked.connect(self._open_backups_dialog)
        top_bar.addWidget(self.backups_btn)

        self.add_acc_btn = QPushButton("+ Add Account")
        self.add_acc_btn.setProperty("class", "primary-btn")
        self.add_acc_btn.setToolTip("Register a new Claude account profile")
        self.add_acc_btn.clicked.connect(self._open_add_dialog)
        top_bar.addWidget(self.add_acc_btn)

        main_layout.addLayout(top_bar)

        # Main Tabs
        self.tabs = QTabWidget()

        # Tab 1: Accounts Dashboard
        self.accounts_tab = QWidget()
        self._setup_accounts_tab()
        self.tabs.addTab(self.accounts_tab, "Accounts")

        # Tab 2: Session Hub (Selective Transfer & Management)
        self.session_hub = SessionHubWidget()
        self.session_hub.session_transferred.connect(self._on_session_hub_transferred)
        self.session_hub.session_deleted.connect(self._on_session_hub_deleted)
        self.tabs.addTab(self.session_hub, "Session Hub (Rate Limits)")

        # Tab 3: Settings
        self.settings_tab = QWidget()
        self._setup_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tabs)

        # Bottom Feedback Bar
        self.feedback_label = QLabel("Ready. Your active session is securely backed up.")
        self.feedback_label.setStyleSheet("color: #9ca3af; font-size: 12px; padding: 4px;")
        main_layout.addWidget(self.feedback_label)

    def _on_tab_changed(self, index: int):
        if index == 1:
            self.session_hub.refresh_sessions()

    def _on_session_hub_transferred(self):
        self.feedback_label.setText("Sessions successfully transferred. Switch accounts to resume.")

    def _on_session_hub_deleted(self, count: int):
        self.feedback_label.setText(f"Successfully deleted {count} session(s) from Claude Desktop.")

    def _setup_accounts_tab(self):
        layout = QVBoxLayout(self.accounts_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)

        self.refresh_accounts_list()

    def refresh_accounts_list(self):
        """Re-render account cards from registry."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        accounts_data = config.load_accounts()
        accounts_map = accounts_data.get("accounts", {})
        active_id = accounts_data.get("active_account_id")

        if not accounts_map:
            empty_lbl = QLabel("No accounts registered yet.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(empty_lbl)
            return

        for acc_id, acc_info in accounts_map.items():
            is_active = (acc_id == active_id)
            card = AccountCard(acc_info, is_active=is_active)
            card.switch_requested.connect(self._handle_switch_account)
            card.edit_requested.connect(self._handle_edit_account)
            card.rename_requested.connect(self._handle_rename_account)
            card.delete_requested.connect(self._handle_delete_account)
            card.shortcut_requested.connect(self._handle_create_shortcut)
            self.cards_layout.addWidget(card)

        # Update system tray menu as well
        self.tray_icon.update_menu()

    def _setup_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        settings = config.load_settings()

        title = QLabel("Application Settings")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        layout.addWidget(title)

        # Checkboxes
        self.mcp_check = QCheckBox("Share custom MCP server configurations across all accounts")
        self.mcp_check.setChecked(settings.get("share_mcp_config", True))
        self.mcp_check.stateChanged.connect(self._save_settings)
        layout.addWidget(self.mcp_check)

        self.carryover_check = QCheckBox("Prompt to carry over in-progress sessions during account switch")
        self.carryover_check.setChecked(settings.get("prompt_session_carryover", True))
        self.carryover_check.stateChanged.connect(self._save_settings)
        layout.addWidget(self.carryover_check)

        self.tray_check = QCheckBox("Minimize to system tray when window is closed")
        self.tray_check.setChecked(settings.get("minimize_to_tray", True))
        self.tray_check.stateChanged.connect(self._save_settings)
        layout.addWidget(self.tray_check)

        # Storage directory info box
        path_box = QFrame()
        path_box.setProperty("class", "card-frame")
        p_layout = QVBoxLayout(path_box)
        p_layout.setContentsMargins(14, 12, 14, 12)

        path_title = QLabel("Profile Storage Location:")
        path_title.setStyleSheet("font-weight: 600; color: #d1d5db;")
        p_layout.addWidget(path_title)

        path_val = QLabel(str(config.profiles_dir))
        path_val.setStyleSheet("color: #f59e0b; font-family: monospace; font-size: 12px;")
        p_layout.addWidget(path_val)

        layout.addWidget(path_box)
        layout.addStretch()

    def _save_settings(self):
        settings = {
            "share_mcp_config": self.mcp_check.isChecked(),
            "prompt_session_carryover": self.carryover_check.isChecked(),
            "minimize_to_tray": self.tray_check.isChecked()
        }
        config.save_settings(settings)
        self.feedback_label.setText("Settings saved successfully.")

    def _update_claude_status_from_worker(self, is_running: bool, count: int):
        if is_running:
            self.status_pill.setText(f"● Claude Running ({count} procs)")
            self.status_pill.setStyleSheet(
                "background-color: rgba(6, 78, 59, 0.7); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.5); "
                "padding: 6px 14px; border-radius: 12px; font-size: 11px; font-weight: 700;"
            )
        else:
            self.status_pill.setText("○ Claude Stopped")
            self.status_pill.setStyleSheet(
                "background-color: rgba(39, 33, 21, 0.7); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); "
                "padding: 6px 14px; border-radius: 12px; font-size: 11px; font-weight: 700;"
            )

    def _handle_switch_account(self, target_account_id: str):
        accounts_data = config.load_accounts()
        current_id = accounts_data.get("active_account_id")
        if target_account_id == current_id:
            return

        target_acc = accounts_data.get("accounts", {}).get(target_account_id)
        if not target_acc:
            return

        carry_over_ids = []
        is_move = True
        settings = config.load_settings()

        # Check if user wants session carryover
        if settings.get("prompt_session_carryover", True):
            current_acc = accounts_data.get("accounts", {}).get(current_id, {})
            current_uuid = current_acc.get("account_uuid")
            if current_uuid:
                sessions = session_manager.get_sessions_for_account(current_uuid)
                if sessions:
                    dlg = SwitchPromptDialog(target_acc.get("name", "Account"), sessions, self)
                    if dlg.exec() == QDialog.DialogCode.Accepted:
                        selected_ids = dlg.get_selected_session_ids()
                        is_move = dlg.is_move_mode()
                        if selected_ids:
                            carry_over_ids.extend(selected_ids)
                    else:
                        return  # User canceled switch

        # Asynchronous non-blocking switch execution
        self.feedback_label.setText(f"Switching to {target_acc.get('name')} (closing Claude Desktop safely)...")
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))

        self._switch_worker = SwitchAccountWorker(
            target_account_id,
            carry_over_ids,
            move_sessions=is_move,
            parent=self
        )
        self._switch_worker.status_changed.connect(lambda msg: self.feedback_label.setText(msg))

        def on_switch_done(success: bool, msg: str):
            self.unsetCursor()
            if success:
                self.feedback_label.setText(f"Active account: {target_acc.get('name')} (Claude Desktop restarted)")
                self.refresh_accounts_list()
                self.session_hub.refresh_sessions()
                self.tray_icon.showMessage(
                    "Account Switched",
                    f"Now active: {target_acc.get('name')}. Claude Desktop restarted and ready.",
                    QIcon(create_tray_pixmap())
                )
            else:
                QMessageBox.critical(self, "Switch Error", f"Could not switch account:\n{msg}")
                self.feedback_label.setText("Switch failed.")

        self._switch_worker.finished.connect(on_switch_done)
        self._switch_worker.start()

    def _open_add_dialog(self):
        dialog = AddAccountDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            acc_name, avatar_color, share_mcp = dialog.get_account_data()
            self.feedback_label.setText(f"Preparing setup for '{acc_name}'...")
            self.setCursor(QCursor(Qt.CursorShape.WaitCursor))

            self._create_worker = CreateAccountWorker(acc_name, avatar_color, share_mcp, parent=self)
            self._create_worker.status_changed.connect(lambda msg: self.feedback_label.setText(msg))

            def on_create_done(success: bool, new_id: str, msg: str):
                self.unsetCursor()
                if success:
                    self.feedback_label.setText(f"Opened Claude in sign-in mode for '{acc_name}'. Please log in.")
                    self.refresh_accounts_list()
                    self.pending_watcher.start(3000)
                else:
                    QMessageBox.critical(self, "Setup Error", f"Could not initialize account setup:\n{msg}")
                    self.feedback_label.setText("Setup failed.")

            self._create_worker.finished.connect(on_create_done)
            self._create_worker.start()

    def _check_pending_logins(self):
        """Detect when the user finishes signing in to their new account."""
        accounts_data = config.load_accounts()
        pending = None
        for acc_id, acc in accounts_data.get("accounts", {}).items():
            if acc.get("is_pending_login"):
                pending = (acc_id, acc)
                break

        if not pending:
            self.pending_watcher.stop()
            return

        acc_id, acc = pending
        info = detector.get_active_session_info()
        if info.get("is_signed_in") and info.get("account_uuid"):
            # Completed sign in!
            profile_manager.save_current_profile()
            acc["is_pending_login"] = False
            acc["account_uuid"] = info["account_uuid"]
            acc["org_uuids"] = info.get("org_uuids", [])
            config.save_accounts(accounts_data)

            self.pending_watcher.stop()
            self.refresh_accounts_list()
            self.session_hub.refresh_sessions()
            self.tray_icon.showMessage(
                "Sign-In Complete",
                f"Account '{acc['name']}' has been registered and secured.",
                QIcon(create_tray_pixmap())
            )

    def _open_backups_dialog(self):
        dlg = BackupDialog(self)
        dlg.restored.connect(self.refresh_accounts_list)
        dlg.exec()

    def _on_restart_claude(self):
        self.feedback_label.setText("Restarting Claude Desktop...")
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))

        self._restart_worker = RestartClaudeWorker(parent=self)
        self._restart_worker.status_changed.connect(lambda msg: self.feedback_label.setText(msg))

        def on_restart_done(success: bool, msg: str):
            self.unsetCursor()
            self.feedback_label.setText("Claude Desktop restarted.")

        self._restart_worker.finished.connect(on_restart_done)
        self._restart_worker.start()

    def _handle_edit_account(self, account_id: str):
        """Open full Edit dialog to change name, avatar color, or remove profile."""
        accounts = config.load_accounts()
        acc = accounts.get("accounts", {}).get(account_id)
        if not acc:
            return

        active_id = accounts.get("active_account_id")
        dlg = EditAccountDialog(acc, is_active=(account_id == active_id), parent=self)
        dlg.account_deleted.connect(lambda a_id: self._handle_delete_account(a_id, confirmed=True))

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name, new_color = dlg.get_updated_data()
            acc["name"] = new_name
            acc["avatar_color"] = new_color
            config.save_accounts(accounts)
            self.refresh_accounts_list()
            self.feedback_label.setText(f"Profile '{new_name}' updated.")

    def _handle_rename_account(self, account_id: str):
        self._handle_edit_account(account_id)

    def _handle_delete_account(self, account_id: str, confirmed: bool = False):
        accounts = config.load_accounts()
        acc = accounts.get("accounts", {}).get(account_id)
        if not acc:
            return

        active_id = accounts.get("active_account_id")
        if account_id == active_id:
            QMessageBox.warning(
                self, "Active Account",
                f"Cannot remove '{acc.get('name')}' because it is currently the active account.\n"
                "Please switch to another account before removing this one."
            )
            return

        if not confirmed:
            confirm = QMessageBox.question(
                self, "Confirm Account Removal",
                f"Are you sure you want to remove profile '{acc.get('name')}' from Claude Switcher?\n\n"
                "This will delete its saved profile files.\n"
                "(Your initial baseline backup is permanently preserved).",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        # Remove profile folder
        profile_dir = config.profiles_dir / account_id
        if profile_dir.exists():
            import shutil
            shutil.rmtree(profile_dir, ignore_errors=True)
        del accounts["accounts"][account_id]
        config.save_accounts(accounts)
        self.refresh_accounts_list()
        self.feedback_label.setText(f"Removed profile '{acc.get('name')}'.")

    def _handle_create_shortcut(self, account_id: str):
        try:
            from create_shortcut import create_desktop_shortcut_for_account
            path = create_desktop_shortcut_for_account(account_id)
            QMessageBox.information(self, "Shortcut Created", f"Desktop shortcut created:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Shortcut Failed", f"Could not create shortcut:\n{e}")

    def _toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        settings = config.load_settings()
        if settings.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Claude Switcher",
                "Minimized to system tray. Click icon to reopen.",
                QIcon(create_tray_pixmap()),
                2000
            )
        else:
            event.accept()
