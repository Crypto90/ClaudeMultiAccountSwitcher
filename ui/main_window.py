"""Main Dashboard window for Claude Multi-Account Switcher."""

import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QScrollArea, QFrame, QMessageBox,
    QInputDialog, QCheckBox, QDialog, QComboBox
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
from ui.backup_dialog import BackupDialog
from ui.tray_icon import ClaudeTrayIcon, create_tray_pixmap


class SwitchPromptDialog(QDialog):
    """Optional quick prompt to carry over a specific session when switching."""

    def __init__(self, target_account_name: str, available_sessions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Switch Account")
        self.setFixedSize(480, 260)
        self.target_account_name = target_account_name
        self.available_sessions = available_sessions
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(f"Switching to {self.target_account_name}")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        layout.addWidget(title)

        desc = QLabel(
            "Would you like to carry over a specific in-progress or rate-limited "
            "session to this account so you can continue working immediately?"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(desc)

        self.session_combo = QComboBox()
        self.session_combo.addItem("None (Open fresh or keep previous work)", None)
        for s in self.available_sessions:
            self.session_combo.addItem(f"{s['title']} ({s['project_name']})", s["session_id"])
        layout.addWidget(self.session_combo)

        layout.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        switch_btn = QPushButton("Switch Now")
        switch_btn.setProperty("class", "primary-btn")
        switch_btn.clicked.connect(self.accept)
        btns.addWidget(switch_btn)

        layout.addLayout(btns)

    def get_selected_session_id(self):
        return self.session_combo.currentData()


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

        # Live Claude process monitor timer (every 2.5s)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._update_claude_status)
        self.monitor_timer.start(2500)
        self._update_claude_status()

        # Pending login watcher timer
        self.pending_watcher = QTimer(self)
        self.pending_watcher.timeout.connect(self._check_pending_logins)

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # Top Bar: App Title + Status Pill + Actions
        top_bar = QHBoxLayout()
        top_bar.setSpacing(14)

        title_lbl = QLabel("✦ Claude Switcher")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #f59e0b;")
        top_bar.addWidget(title_lbl)

        # Live Claude Status Pill
        self.status_pill = QLabel("Checking Claude status...")
        self.status_pill.setStyleSheet(
            "padding: 5px 12px; border-radius: 12px; font-size: 11px; font-weight: 700;"
        )
        top_bar.addWidget(self.status_pill)
        top_bar.addStretch()

        # Action Buttons
        self.restart_btn = QPushButton("Restart Claude")
        self.restart_btn.clicked.connect(self._on_restart_claude)
        top_bar.addWidget(self.restart_btn)

        self.backups_btn = QPushButton("Safety & Backups")
        self.backups_btn.clicked.connect(self._open_backups_dialog)
        top_bar.addWidget(self.backups_btn)

        self.add_acc_btn = QPushButton("+ Add Account")
        self.add_acc_btn.setProperty("class", "primary-btn")
        self.add_acc_btn.clicked.connect(self._open_add_dialog)
        top_bar.addWidget(self.add_acc_btn)

        main_layout.addLayout(top_bar)

        # Main Tabs
        self.tabs = QTabWidget()

        # Tab 1: Accounts Dashboard
        self.accounts_tab = QWidget()
        self._setup_accounts_tab()
        self.tabs.addTab(self.accounts_tab, "Accounts")

        # Tab 2: Session Hub (Selective Transfer)
        self.session_hub = SessionHubWidget()
        self.tabs.addTab(self.session_hub, "Session Hub (Rate Limits)")

        # Tab 3: Settings
        self.settings_tab = QWidget()
        self._setup_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")

        main_layout.addWidget(self.tabs)

        # Bottom Feedback Bar
        self.feedback_label = QLabel("Ready. Your active session is securely backed up.")
        self.feedback_label.setStyleSheet("color: #9ca3af; font-size: 12px; padding: 4px;")
        main_layout.addWidget(self.feedback_label)

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

    def _update_claude_status(self):
        procs = detector.get_claude_processes()
        if procs:
            total_mem = sum(p["memory_mb"] for p in procs)
            self.status_pill.setText(f"● Claude Running ({len(procs)} procs, {total_mem:.0f} MB)")
            self.status_pill.setStyleSheet(
                "background-color: #064e3b; color: #34d399; border: 1px solid #059669; "
                "padding: 5px 12px; border-radius: 12px; font-size: 11px; font-weight: 700;"
            )
        else:
            self.status_pill.setText("○ Claude Stopped")
            self.status_pill.setStyleSheet(
                "background-color: #272115; color: #f59e0b; border: 1px solid #78350f; "
                "padding: 5px 12px; border-radius: 12px; font-size: 11px; font-weight: 700;"
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
                        selected_sess = dlg.get_selected_session_id()
                        if selected_sess:
                            carry_over_ids.append(selected_sess)
                    else:
                        return  # User canceled switch

        self.feedback_label.setText(f"Switching to {target_acc.get('name')}...")
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))

        try:
            profile_manager.switch_account(target_account_id, carry_over_session_ids=carry_over_ids)
            self.feedback_label.setText(f"Active account is now: {target_acc.get('name')}")
            self.refresh_accounts_list()
            self.session_hub.refresh_sessions()
            self.tray_icon.showMessage(
                "Account Switched",
                f"Now active: {target_acc.get('name')}. Claude Desktop is ready.",
                QIcon(create_tray_pixmap())
            )
        except Exception as e:
            QMessageBox.critical(self, "Switch Error", f"Could not switch account:\n{e}")
            self.feedback_label.setText("Switch failed.")
        finally:
            self.unsetCursor()

    def _open_add_dialog(self):
        dialog = AddAccountDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            acc_name, avatar_color, share_mcp = dialog.get_account_data()
            try:
                new_id = profile_manager.create_new_account_setup(acc_name, avatar_color, share_mcp)
                self.feedback_label.setText(f"Opened Claude in sign-in mode for '{acc_name}'. Please log in.")
                self.refresh_accounts_list()
                # Start watcher
                self.pending_watcher.start(3000)
            except Exception as e:
                QMessageBox.critical(self, "Setup Error", f"Could not initialize account setup:\n{e}")

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
        process_manager.restart_claude()
        self.feedback_label.setText("Claude Desktop restarted.")

    def _handle_rename_account(self, account_id: str):
        accounts = config.load_accounts()
        acc = accounts.get("accounts", {}).get(account_id)
        if not acc:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Account", "Enter new account name:", text=acc.get("name")
        )
        if ok and new_name.strip():
            acc["name"] = new_name.strip()
            config.save_accounts(accounts)
            self.refresh_accounts_list()

    def _handle_delete_account(self, account_id: str):
        accounts = config.load_accounts()
        acc = accounts.get("accounts", {}).get(account_id)
        if not acc:
            return

        confirm = QMessageBox.question(
            self, "Delete Account",
            f"Are you sure you want to remove profile '{acc.get('name')}'?\n"
            "This will remove the local profile folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            # Remove profile folder
            profile_dir = config.profiles_dir / account_id
            if profile_dir.exists():
                import shutil
                shutil.rmtree(profile_dir, ignore_errors=True)
            del accounts["accounts"][account_id]
            config.save_accounts(accounts)
            self.refresh_accounts_list()

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
