"""Session Hub: Interactive, selective session browser, cross-account transfer, and session deletion."""

import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QCheckBox,
    QDialog, QMessageBox, QFrame, QAbstractItemView, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor

from core.session_manager import session_manager
from core.config import config


class TransferSessionsDialog(QDialog):
    """Modal dialog to select destination account and transfer mode for selected sessions."""

    def __init__(self, selected_sessions: list, accounts: dict, current_account_id: str, parent=None):
        super().__init__(parent)
        self.selected_sessions = selected_sessions
        self.accounts = accounts
        self.current_account_id = current_account_id

        self.setWindowTitle("Transfer Selected Sessions")
        self.setFixedSize(500, 380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title_label = QLabel(f"Transfer {len(self.selected_sessions)} Selected Session(s)")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        layout.addWidget(title_label)

        desc = QLabel(
            "Copy or move in-progress sessions (e.g., when rate-limited) to another account "
            "so you can resume work without losing context."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(desc)

        # Selected Sessions Summary Box
        summary_frame = QFrame()
        summary_frame.setProperty("class", "card-frame")
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(4)

        for s in self.selected_sessions[:4]:
            item_lbl = QLabel(f"• {s['title']} ({s['project_name']})")
            item_lbl.setStyleSheet("color: #d1d5db; font-size: 12px;")
            summary_layout.addWidget(item_lbl)

        if len(self.selected_sessions) > 4:
            more_lbl = QLabel(f"  ...and {len(self.selected_sessions) - 4} more")
            more_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            summary_layout.addWidget(more_lbl)

        layout.addWidget(summary_frame)

        # Destination Account Picker
        dest_layout = QVBoxLayout()
        dest_layout.setSpacing(6)
        dest_label = QLabel("Destination Account:")
        dest_label.setStyleSheet("font-weight: 600; color: #f3f4f6;")
        dest_layout.addWidget(dest_label)

        self.account_combo = QComboBox()
        for acc_id, acc_data in self.accounts.items():
            if acc_id != self.current_account_id:
                uuid_display = acc_data.get("account_uuid", "Pending UUID")[:8]
                self.account_combo.addItem(f"{acc_data.get('name')} ({uuid_display})", acc_id)

        dest_layout.addWidget(self.account_combo)
        layout.addLayout(dest_layout)

        # Transfer mode checkbox
        self.move_checkbox = QCheckBox("Move session (delete from source account instead of copying)")
        layout.addWidget(self.move_checkbox)

        layout.addStretch()

        # Action Buttons
        btns_layout = QHBoxLayout()
        btns_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(cancel_btn)

        self.transfer_btn = QPushButton("Confirm Transfer")
        self.transfer_btn.setProperty("class", "primary-btn")
        self.transfer_btn.clicked.connect(self.accept)
        btns_layout.addWidget(self.transfer_btn)

        layout.addLayout(btns_layout)

    def get_transfer_params(self):
        """Returns (target_account_id, is_move)."""
        target_id = self.account_combo.currentData()
        return target_id, self.move_checkbox.isChecked()


class SessionHubWidget(QWidget):
    """Widget allowing granular search, selective filtering, 1-click cross-account session transfer, and session deletion."""

    session_transferred = pyqtSignal()
    session_deleted = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sessions = []
        self._setup_ui()
        self.refresh_sessions()

    def _get_account_info(self, account_uuid: str) -> tuple:
        """Returns (account_name, avatar_color)."""
        accounts = config.load_accounts().get("accounts", {})
        for acc in accounts.values():
            if acc.get("account_uuid") == account_uuid:
                return acc.get("name", "Account"), acc.get("avatar_color", "#9ca3af")
        return "Unknown Account", "#6b7280"

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Info Banner
        header_layout = QHBoxLayout()
        header_title = QLabel("Session Hub")
        header_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        header_layout.addWidget(header_title)

        header_sub = QLabel("Select specific sessions to copy or delete across accounts for rate-limit continuity.")
        header_sub.setStyleSheet("color: #9ca3af; font-size: 13px; margin-left: 8px;")
        header_layout.addWidget(header_sub)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedWidth(90)
        self.refresh_btn.clicked.connect(self.refresh_sessions)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # Filter & Action Toolbar
        toolbar_frame = QFrame()
        toolbar_frame.setProperty("class", "banner-frame")
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(12, 10, 12, 10)
        toolbar_layout.setSpacing(12)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search sessions by title or project...")
        self.search_input.setFixedWidth(280)
        self.search_input.textChanged.connect(self._apply_filter)
        toolbar_layout.addWidget(self.search_input)

        # Account Filter Combo
        self.filter_account_combo = QComboBox()
        self.filter_account_combo.setFixedWidth(180)
        self.filter_account_combo.addItem("All Accounts", "all")
        self.filter_account_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar_layout.addWidget(self.filter_account_combo)

        toolbar_layout.addStretch()

        # Selection Helpers
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        toolbar_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Clear")
        deselect_all_btn.clicked.connect(self._deselect_all)
        toolbar_layout.addWidget(deselect_all_btn)

        # Transfer Selected Button
        self.transfer_btn = QPushButton("Transfer Selected (0)")
        self.transfer_btn.setProperty("class", "primary-btn")
        self.transfer_btn.setEnabled(False)
        self.transfer_btn.clicked.connect(self._on_transfer_clicked)
        toolbar_layout.addWidget(self.transfer_btn)

        # Delete Selected Button
        self.delete_btn = QPushButton("Delete Selected (0)")
        self.delete_btn.setProperty("class", "danger-btn")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        toolbar_layout.addWidget(self.delete_btn)

        layout.addWidget(toolbar_frame)

        # Sessions Table: 7 columns (Check, Title, Account, Project, Turns, Last Active, Actions)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["", "Session Title", "Account", "Project", "Turns", "Last Active", "Actions"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 36)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 140)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 175)

        layout.addWidget(self.table)

    def refresh_sessions(self):
        """Reload sessions from disk and update table."""
        self.sessions = session_manager.get_all_sessions()
        self._update_account_filter_combo()
        self._render_table(self.sessions)

    def _update_account_filter_combo(self):
        accounts_data = config.load_accounts().get("accounts", {})
        current_selection = self.filter_account_combo.currentData()

        self.filter_account_combo.blockSignals(True)
        self.filter_account_combo.clear()
        self.filter_account_combo.addItem("All Accounts", "all")

        for acc_id, acc in accounts_data.items():
            uuid_disp = (acc.get("account_uuid") or "")[:8]
            self.filter_account_combo.addItem(f"{acc.get('name')} ({uuid_disp})", acc.get("account_uuid"))

        # Restore previous selection if possible
        idx = self.filter_account_combo.findData(current_selection)
        if idx != -1:
            self.filter_account_combo.setCurrentIndex(idx)
        self.filter_account_combo.blockSignals(False)

    def _render_table(self, session_list: list):
        self.table.setRowCount(len(session_list))

        for row, sess in enumerate(session_list):
            self.table.setRowHeight(row, 48)

            # Checkbox widget
            cb = QCheckBox()
            cb.setStyleSheet("margin-left: 10px;")
            cb.stateChanged.connect(self._on_selection_changed)
            self.table.setCellWidget(row, 0, cb)

            # Title
            title_item = QTableWidgetItem(sess["title"])
            title_item.setData(Qt.ItemDataRole.UserRole, sess)
            title_item.setToolTip(f"{sess['title']}\nSession ID: {sess['session_id']}")
            self.table.setItem(row, 1, title_item)

            # Account with colored bullet
            acc_name, acc_color = self._get_account_info(sess.get("account_uuid"))
            acc_item = QTableWidgetItem(f"●  {acc_name}")
            acc_item.setForeground(QColor(acc_color))
            acc_item.setToolTip(f"Account: {acc_name}\nUUID: {sess.get('account_uuid')}")
            self.table.setItem(row, 2, acc_item)

            # Project
            proj_item = QTableWidgetItem(sess["project_name"])
            proj_item.setToolTip(sess.get("cwd", ""))
            self.table.setItem(row, 3, proj_item)

            # Turns
            turns_item = QTableWidgetItem(f"{sess['turns']} turns")
            turns_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, turns_item)

            # Last Active
            date_item = QTableWidgetItem(sess["last_activity_str"])
            self.table.setItem(row, 5, date_item)

            # Actions Container (Transfer + Delete)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)
            actions_layout.setSpacing(6)

            quick_transfer_btn = QPushButton("Transfer →")
            quick_transfer_btn.setProperty("class", "table-btn")
            quick_transfer_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            quick_transfer_btn.clicked.connect(lambda _, s=sess: self._quick_transfer_single(s))
            actions_layout.addWidget(quick_transfer_btn)

            quick_del_btn = QPushButton("Delete")
            quick_del_btn.setProperty("class", "table-danger-btn")
            quick_del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            quick_del_btn.clicked.connect(lambda _, s=sess: self._delete_single(s))
            actions_layout.addWidget(quick_del_btn)

            self.table.setCellWidget(row, 6, actions_widget)

        self._on_selection_changed()

    def _apply_filter(self):
        query = self.search_input.text().strip().lower()
        acc_filter = self.filter_account_combo.currentData()

        filtered = []
        for s in self.sessions:
            if acc_filter != "all" and s["account_uuid"] != acc_filter:
                continue
            if query:
                in_title = query in s["title"].lower()
                in_proj = query in s["project_name"].lower()
                in_cwd = query in s["cwd"].lower()
                if not (in_title or in_proj or in_cwd):
                    continue
            filtered.append(s)

        self._render_table(filtered)

    def _get_selected_sessions(self) -> list:
        selected = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb and cb.isChecked():
                title_item = self.table.item(row, 1)
                if title_item:
                    selected.append(title_item.data(Qt.ItemDataRole.UserRole))
        return selected

    def _on_selection_changed(self):
        count = len(self._get_selected_sessions())
        self.transfer_btn.setText(f"Transfer Selected ({count})")
        self.transfer_btn.setEnabled(count > 0)
        self.delete_btn.setText(f"Delete Selected ({count})")
        self.delete_btn.setEnabled(count > 0)

    def _select_all(self):
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb:
                cb.setChecked(True)

    def _deselect_all(self):
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb:
                cb.setChecked(False)

    def _quick_transfer_single(self, session: dict):
        self._execute_transfer_dialog([session])

    def _on_transfer_clicked(self):
        selected = self._get_selected_sessions()
        if not selected:
            return
        self._execute_transfer_dialog(selected)

    def _delete_single(self, session: dict):
        acc_name, _ = self._get_account_info(session.get("account_uuid"))
        reply = QMessageBox.question(
            self,
            "Delete Session",
            f"Are you sure you want to permanently delete this session?\n\n"
            f"Title: {session.get('title')}\n"
            f"Account: {acc_name}\n"
            f"Project: {session.get('project_name')}\n\n"
            "This will remove the session JSON file from Claude Desktop.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success = session_manager.delete_session(session)
            if success:
                self.refresh_sessions()
                self.session_deleted.emit(1)
            else:
                QMessageBox.critical(self, "Delete Failed", "Could not delete the session file.")

    def _on_delete_clicked(self):
        selected = self._get_selected_sessions()
        if not selected:
            return
        count = len(selected)
        reply = QMessageBox.question(
            self,
            "Delete Selected Sessions",
            f"Are you sure you want to permanently delete {count} selected session(s)?\n\n"
            "This will remove the session JSON file(s) from Claude Desktop.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            res = session_manager.delete_sessions(selected)
            deleted = res.get("deleted_count", 0)
            if deleted > 0:
                self.refresh_sessions()
                self.session_deleted.emit(deleted)
            if res.get("errors"):
                errs = "\n".join(res["errors"])
                QMessageBox.warning(self, "Delete Warnings", f"Some sessions could not be deleted:\n{errs}")

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        title_item = self.table.item(row, 1)
        if not title_item:
            return
        sess = title_item.data(Qt.ItemDataRole.UserRole)
        if not sess:
            return

        menu = QMenu(self)
        transfer_act = menu.addAction("Transfer Session...")
        delete_act = menu.addAction("Delete Session")
        menu.addSeparator()
        explorer_act = menu.addAction("Show in File Explorer")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == transfer_act:
            self._quick_transfer_single(sess)
        elif chosen == delete_act:
            self._delete_single(sess)
        elif chosen == explorer_act:
            self._open_in_explorer(sess)

    def _open_in_explorer(self, sess: dict):
        fp = sess.get("file_path")
        if fp and os.path.exists(fp):
            subprocess.Popen(f'explorer /select,"{os.path.normpath(fp)}"')
        else:
            QMessageBox.warning(self, "File Not Found", "The session file does not exist on disk.")

    def _execute_transfer_dialog(self, sessions_to_transfer: list):
        accounts_data = config.load_accounts()
        accounts_map = accounts_data.get("accounts", {})
        active_id = accounts_data.get("active_account_id")

        if len(accounts_map) < 2:
            QMessageBox.information(
                self, "Second Account Required",
                "You need at least two registered accounts to transfer sessions.\n"
                "Please add a second account first using '+ Add Account'."
            )
            return

        dialog = TransferSessionsDialog(sessions_to_transfer, accounts_map, active_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dest_acc_id, is_move = dialog.get_transfer_params()
            if not dest_acc_id:
                return

            dest_acc = accounts_map.get(dest_acc_id, {})
            dest_uuid = dest_acc.get("account_uuid")
            if not dest_uuid:
                QMessageBox.warning(
                    self, "Incomplete Profile",
                    f"Account '{dest_acc.get('name')}' does not have a recorded UUID yet.\n"
                    "Please switch to it once so Claude Desktop can initialize its session storage."
                )
                return

            session_ids = [s["session_id"] for s in sessions_to_transfer]
            source_uuid = sessions_to_transfer[0]["account_uuid"]

            res = session_manager.transfer_selected_sessions(
                session_ids=session_ids,
                from_account_uuid=source_uuid,
                to_account_uuid=dest_uuid,
                move=is_move
            )

            if res["transferred_count"] > 0:
                QMessageBox.information(
                    self, "Transfer Complete",
                    f"Successfully transferred {res['transferred_count']} session(s) to '{dest_acc.get('name')}'.\n"
                    "You can now switch to that account and continue working!"
                )
                self.refresh_sessions()
                self.session_transferred.emit()
            else:
                errs = "\n".join(res["errors"])
                QMessageBox.critical(self, "Transfer Failed", f"Could not transfer sessions:\n{errs}")

