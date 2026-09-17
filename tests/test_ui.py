"""Unit tests for UI components using offscreen Qt platform."""

import os
import sys
import unittest
from PyQt6.QtWidgets import QApplication

# Set offscreen platform so tests run headlessly without opening windows
os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestUI(unittest.TestCase):
    """Test UI widget creation, layout, and tabs."""

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_session_hub_widget_creation(self):
        from ui.session_hub import SessionHubWidget
        hub = SessionHubWidget()
        self.assertIsNotNone(hub.table)
        self.assertEqual(hub.table.columnCount(), 6)
        self.assertIsNotNone(hub.search_input)
        self.assertIsNotNone(hub.transfer_btn)

    def test_account_card_creation(self):
        from ui.account_card import AccountCard
        mock_data = {
            "id": "acc_test",
            "name": "Test Account",
            "avatar_color": "#8b5cf6",
            "account_uuid": "12345678-abcd-1234-abcd-1234567890ab",
            "last_active": "2026-09-17T11:00:00"
        }
        card = AccountCard(mock_data, is_active=False)
        self.assertEqual(card.account_id, "acc_test")
        self.assertFalse(card.is_active)

        active_card = AccountCard(mock_data, is_active=True)
        self.assertTrue(active_card.is_active)

    def test_add_dialog_creation(self):
        from ui.add_dialog import AddAccountDialog
        dialog = AddAccountDialog()
        self.assertIsNotNone(dialog.name_input)
        self.assertIsNotNone(dialog.mcp_checkbox)

    def test_edit_dialog_creation(self):
        from ui.edit_dialog import EditAccountDialog
        mock_data = {
            "id": "acc_edit",
            "name": "Original Name",
            "avatar_color": "#d97706",
            "account_uuid": "12345678-abcd-1234-abcd-1234567890ab"
        }
        dialog = EditAccountDialog(mock_data, is_active=False)
        self.assertEqual(dialog.name_input.text(), "Original Name")
        self.assertTrue(dialog.delete_btn.isEnabled())

        active_dialog = EditAccountDialog(mock_data, is_active=True)
        self.assertFalse(active_dialog.delete_btn.isEnabled())

    def test_worker_instantiation(self):
        from ui.worker import SwitchAccountWorker, RestartClaudeWorker
        w1 = SwitchAccountWorker("acc_test")
        self.assertIsNotNone(w1)
        w2 = RestartClaudeWorker()
        self.assertIsNotNone(w2)

    def test_switch_prompt_dialog_multi_select(self):
        from ui.main_window import SwitchPromptDialog
        sessions = [
            {
                "session_id": "sess_1",
                "title": "Session 1",
                "project_name": "Project Alpha",
                "turns": 5,
                "last_activity_str": "10m ago"
            },
            {
                "session_id": "sess_2",
                "title": "Session 2",
                "project_name": "Project Beta",
                "turns": 12,
                "last_activity_str": "1h ago"
            },
            {
                "session_id": "sess_3",
                "title": "Session 3",
                "project_name": "Project Gamma",
                "turns": 2,
                "last_activity_str": "2h ago"
            }
        ]
        dialog = SwitchPromptDialog("Secondary Account", sessions)
        self.assertEqual(len(dialog.session_checkboxes), 3)
        self.assertEqual(dialog.get_selected_session_ids(), [])
        self.assertIn("Keep Separate", dialog.switch_btn.text())

        # Select all
        dialog._select_all()
        self.assertEqual(dialog.get_selected_session_ids(), ["sess_1", "sess_2", "sess_3"])
        self.assertIn("Copy (3)", dialog.switch_btn.text())

        # Select none
        dialog._select_none()
        self.assertEqual(dialog.get_selected_session_ids(), [])

        # Select recent
        dialog._select_recent()
        self.assertEqual(dialog.get_selected_session_ids(), ["sess_1"])

        # Manual multi-select
        dialog._select_none()
        dialog.session_checkboxes[0][0].setChecked(True)
        dialog.session_checkboxes[2][0].setChecked(True)
        self.assertEqual(dialog.get_selected_session_ids(), ["sess_1", "sess_3"])
        self.assertIn("Copy (2)", dialog.switch_btn.text())


if __name__ == "__main__":
    unittest.main()

