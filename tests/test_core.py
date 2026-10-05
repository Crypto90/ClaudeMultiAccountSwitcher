"""Unit tests for Claude Multi-Account Switcher core modules."""

import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.config import AppConfig, EXCLUDED_PROFILE_ITEMS
from core.detector import ClaudeDetector
from core.session_manager import SessionManager
from core.profile_manager import ProfileManager


class TestCoreModules(unittest.TestCase):
    """Test core logic in isolated temporary directory."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="claude_test_")
        self.app_dir = Path(self.test_dir) / "app_data"
        self.mock_claude_dir = Path(self.test_dir) / "mock_claude"
        self.mock_claude_dir.mkdir(parents=True, exist_ok=True)

        self.config = AppConfig(custom_app_data_dir=str(self.app_dir))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_config_paths_and_defaults(self):
        settings = self.config.load_settings()
        self.assertTrue(settings["share_mcp_config"])
        self.assertTrue(settings["auto_backup_on_switch"])

        accounts = self.config.load_accounts()
        self.assertFalse(accounts["initial_backup_created"])
        self.assertEqual(accounts["accounts"], {})

    def test_session_payload_copy_excludes_heavy_items(self):
        """Verify that 12 GB vm_bundles and binaries are explicitly excluded from copies."""
        # Create mock session files
        (self.mock_claude_dir / "config.json").write_text('{"windowSizeWasSignedIn": true}', encoding="utf-8")
        (self.mock_claude_dir / "Local State").write_text('{"os_crypt": {}}', encoding="utf-8")
        net_dir = self.mock_claude_dir / "Network"
        net_dir.mkdir()
        (net_dir / "Cookies").write_bytes(b"mock_sqlite_data")

        # Create heavy items that MUST NOT be copied
        vm_dir = self.mock_claude_dir / "vm_bundles"
        vm_dir.mkdir()
        (vm_dir / "claudevm.bundle").write_bytes(b"x" * 1024)

        code_dir = self.mock_claude_dir / "claude-code"
        code_dir.mkdir()
        (code_dir / "claude.exe").write_bytes(b"x" * 1024)

        cache_dir = self.mock_claude_dir / "Cache"
        cache_dir.mkdir()
        (cache_dir / "data_0").write_bytes(b"cache")

        dest_dir = Path(self.test_dir) / "copied_profile"
        pm = ProfileManager()
        copied = pm.copy_session_payload(self.mock_claude_dir, dest_dir)

        self.assertTrue((dest_dir / "config.json").exists())
        self.assertTrue((dest_dir / "Local State").exists())
        self.assertTrue((dest_dir / "Network" / "Cookies").exists())

        # Heavy items must be completely absent
        self.assertFalse((dest_dir / "vm_bundles").exists())
        self.assertFalse((dest_dir / "claude-code").exists())
        self.assertFalse((dest_dir / "Cache").exists())

    def test_selective_session_transfer(self):
        """Verify that only specifically selected sessions are transferred between accounts."""
        acc_a = "uuid_alpha"
        acc_b = "uuid_beta"
        org_id = "org_gamma"

        sess_dir_a = self.mock_claude_dir / "claude-code-sessions" / acc_a / org_id
        sess_dir_a.mkdir(parents=True, exist_ok=True)

        # Create 3 sessions in Account A
        session_1 = {
            "sessionId": "local_sess_1",
            "title": "Fix Auth Bug",
            "cwd": "C:/Projects/Project1",
            "createdAt": 1000,
            "lastActivityAt": 2000
        }
        session_2 = {
            "sessionId": "local_sess_2",
            "title": "Rate Limited Task",
            "cwd": "C:/Projects/Project2",
            "createdAt": 3000,
            "lastActivityAt": 4000
        }
        session_3 = {
            "sessionId": "local_sess_3",
            "title": "Draft Feature",
            "cwd": "C:/Projects/Project3",
            "createdAt": 5000,
            "lastActivityAt": 6000
        }

        (sess_dir_a / "local_sess_1.json").write_text(json.dumps(session_1), encoding="utf-8")
        (sess_dir_a / "local_sess_2.json").write_text(json.dumps(session_2), encoding="utf-8")
        (sess_dir_a / "local_sess_3.json").write_text(json.dumps(session_3), encoding="utf-8")

        # Discover sessions in Account A
        discovered = SessionManager.get_sessions_for_account(acc_a, claude_dir=self.mock_claude_dir)
        self.assertEqual(len(discovered), 3)

        # Transfer ONLY session 2 to Account B
        res = SessionManager.transfer_selected_sessions(
            session_ids=["local_sess_2"],
            from_account_uuid=acc_a,
            to_account_uuid=acc_b,
            claude_dir=self.mock_claude_dir
        )
        self.assertEqual(res["transferred_count"], 1)
        self.assertIn("Rate Limited Task", res["transferred_sessions"])

        # Check Account B's sessions: should have ONLY session 2!
        acc_b_sessions = SessionManager.get_sessions_for_account(acc_b, claude_dir=self.mock_claude_dir)
        self.assertEqual(len(acc_b_sessions), 1)
        self.assertEqual(acc_b_sessions[0]["session_id"], "local_sess_2")
        self.assertEqual(acc_b_sessions[0]["title"], "Rate Limited Task")

        # Account A still has its sessions (since move=False)
        acc_a_sessions = SessionManager.get_sessions_for_account(acc_a, claude_dir=self.mock_claude_dir)
        self.assertEqual(len(acc_a_sessions), 3)

    def test_selective_session_move(self):
        """Verify that transferring sessions with move=True removes them from the source account."""
        acc_a = "uuid_move_src"
        acc_b = "uuid_move_dst"
        org_id = "org_move"

        sess_dir_a = self.mock_claude_dir / "claude-code-sessions" / acc_a / org_id
        sess_dir_a.mkdir(parents=True, exist_ok=True)

        session_1 = {
            "sessionId": "local_move_1",
            "title": "Move Task",
            "cwd": "C:/Projects/MoveProj",
            "createdAt": 1000
        }
        (sess_dir_a / "local_move_1.json").write_text(json.dumps(session_1), encoding="utf-8")

        # Move to Account B
        res = SessionManager.transfer_selected_sessions(
            session_ids=["local_move_1"],
            from_account_uuid=acc_a,
            to_account_uuid=acc_b,
            move=True,
            claude_dir=self.mock_claude_dir
        )
        self.assertEqual(res["transferred_count"], 1)

        # Verify Account A no longer has the session
        acc_a_sessions = SessionManager.get_sessions_for_account(acc_a, claude_dir=self.mock_claude_dir)
        self.assertEqual(len(acc_a_sessions), 0)

        # Verify Account B has the session
        acc_b_sessions = SessionManager.get_sessions_for_account(acc_b, claude_dir=self.mock_claude_dir)
        self.assertEqual(len(acc_b_sessions), 1)
        self.assertEqual(acc_b_sessions[0]["session_id"], "local_move_1")

    def test_delete_session(self):
        """Verify deleting a single session removes the JSON file and cleans empty directory."""
        acc_uuid = "uuid_del_test"
        org_id = "org_del_test"
        sess_dir = self.mock_claude_dir / "claude-code-sessions" / acc_uuid / org_id
        sess_dir.mkdir(parents=True, exist_ok=True)

        session_data = {
            "sessionId": "local_del_1",
            "title": "Unwanted Duplicate Session",
            "cwd": "C:/Projects/DupProject"
        }
        file_path = sess_dir / "local_del_1.json"
        file_path.write_text(json.dumps(session_data), encoding="utf-8")

        self.assertTrue(file_path.exists())

        # Delete session
        sess_dict = {
            "session_id": "local_del_1",
            "account_uuid": acc_uuid,
            "title": "Unwanted Duplicate Session",
            "file_path": str(file_path)
        }
        success = SessionManager.delete_session(sess_dict, claude_dir=self.mock_claude_dir)
        self.assertTrue(success)
        self.assertFalse(file_path.exists())
        # Empty org directory should be cleaned up
        self.assertFalse(sess_dir.exists())

    def test_delete_sessions_batch(self):
        """Verify batch session deletion removes all specified session files."""
        acc_uuid = "uuid_batch_del"
        org_id = "org_batch_del"
        sess_dir = self.mock_claude_dir / "claude-code-sessions" / acc_uuid / org_id
        sess_dir.mkdir(parents=True, exist_ok=True)

        f1 = sess_dir / "local_b1.json"
        f2 = sess_dir / "local_b2.json"
        f1.write_text(json.dumps({"title": "Session B1"}), encoding="utf-8")
        f2.write_text(json.dumps({"title": "Session B2"}), encoding="utf-8")

        sessions_to_del = [
            {"title": "Session B1", "file_path": str(f1)},
            {"title": "Session B2", "file_path": str(f2)}
        ]
        res = SessionManager.delete_sessions(sessions_to_del, claude_dir=self.mock_claude_dir)
        self.assertEqual(res["deleted_count"], 2)
        self.assertEqual(len(res["errors"]), 0)
        self.assertFalse(f1.exists())
        self.assertFalse(f2.exists())

    def test_delete_session_security_check(self):
        """Verify security checks refuse to delete non-session files or files outside claude-code-sessions."""
        # Create config.json outside sessions directory
        config_path = self.mock_claude_dir / "config.json"
        config_path.write_text('{"test": true}', encoding="utf-8")
        self.assertTrue(config_path.exists())

        unsafe_sess = {
            "title": "Unsafe Hack",
            "file_path": str(config_path)
        }
        success = SessionManager.delete_session(unsafe_sess, claude_dir=self.mock_claude_dir)
        self.assertFalse(success)
        self.assertTrue(config_path.exists())

    def test_launch_claude_verified(self):
        """Verify ProcessManager.launch_claude launches and verifies Claude process presence."""
        from unittest.mock import patch
        from core.process_manager import ProcessManager

        with patch("os.startfile") as mock_startfile, \
             patch("core.detector.ClaudeDetector.is_claude_running", return_value=True), \
             patch("core.detector.ClaudeDetector.get_claude_process_count", return_value=4):
            result = ProcessManager.launch_claude(timeout_sec=1.0)
            self.assertTrue(result)
            mock_startfile.assert_called_once()

    def test_switch_account_restarts_claude_with_status_callback(self):
        """Verify ProfileManager.switch_account restarts Claude and provides real-time status updates."""
        from unittest.mock import patch, MagicMock
        from core.profile_manager import ProfileManager

        pm = ProfileManager()
        pm.config = self.config

        # Setup registry with 2 accounts
        self.config.save_accounts({
            "active_account_id": "acc_1",
            "accounts": {
                "acc_1": {"name": "Account One", "account_uuid": "u1"},
                "acc_2": {"name": "Account Two", "account_uuid": "u2"}
            }
        })
        # Create target profile directory
        target_dir = self.config.profiles_dir / "acc_2"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "config.json").write_text('{"lastKnownAccountUuid": "u2"}', encoding="utf-8")

        statuses = []
        with patch.object(pm.process_manager, "close_claude") as mock_close, \
             patch.object(pm.process_manager, "launch_claude", return_value=True) as mock_launch, \
             patch.object(pm.detector, "is_claude_running", return_value=False), \
             patch.object(self.config, "get_claude_profile_dir", return_value=self.mock_claude_dir):
            success = pm.switch_account(
                "acc_2",
                restart_claude=True,
                status_callback=lambda s: statuses.append(s)
            )
            self.assertTrue(success)
            mock_launch.assert_called_once()
    def test_switch_account_auto_heals_missing_primary_cookies(self):
        """Verify ProfileManager.switch_account auto-heals missing Cookies in primary account from baseline backup."""
        from unittest.mock import patch
        from core.profile_manager import ProfileManager

        pm = ProfileManager()
        pm.config = self.config

        # Create baseline backup with cookies
        backup_net = self.config.initial_backup_dir / "Network"
        backup_net.mkdir(parents=True, exist_ok=True)
        (backup_net / "Cookies").write_bytes(b"baseline_cookies_data")

        # Setup primary account without cookies (simulating the bug)
        primary_dir = self.config.profiles_dir / "account_primary"
        primary_net = primary_dir / "Network"
        primary_net.mkdir(parents=True, exist_ok=True)
        (primary_dir / "config.json").write_text('{"lastKnownAccountUuid": "u_prim"}', encoding="utf-8")

        self.config.save_accounts({
            "active_account_id": "account_other",
            "accounts": {
                "account_primary": {"name": "Main Account", "account_uuid": "u_prim"},
                "account_other": {"name": "Other Account", "account_uuid": "u_other"}
            }
        })

        with patch.object(pm.process_manager, "close_claude"), \
             patch.object(pm.process_manager, "launch_claude", return_value=True), \
             patch.object(pm.detector, "is_claude_running", return_value=False), \
             patch.object(self.config, "get_claude_profile_dir", return_value=self.mock_claude_dir):
            success = pm.switch_account("account_primary", restart_claude=False)
            self.assertTrue(success)

            # Target profile must have auto-healed cookies
            self.assertTrue((primary_dir / "Network" / "Cookies").exists())
            self.assertEqual((primary_dir / "Network" / "Cookies").read_bytes(), b"baseline_cookies_data")
            # Active dir must also have received the cookies
            self.assertTrue((self.mock_claude_dir / "Network" / "Cookies").exists())
            self.assertEqual((self.mock_claude_dir / "Network" / "Cookies").read_bytes(), b"baseline_cookies_data")

    def test_detector_requires_cookies_for_signed_in(self):
        """Verify ClaudeDetector reports is_signed_in=False if Network/Cookies is missing."""
        (self.mock_claude_dir / "config.json").write_text('{"windowSizeWasSignedIn": true}', encoding="utf-8")
        info_no_cookies = ClaudeDetector.get_active_session_info(self.mock_claude_dir)
        self.assertFalse(info_no_cookies["is_signed_in"])
        self.assertFalse(info_no_cookies["has_cookies"])

        net_dir = self.mock_claude_dir / "Network"
        net_dir.mkdir(parents=True, exist_ok=True)
        (net_dir / "Cookies").write_bytes(b"dummy_cookie_payload")

        info_with_cookies = ClaudeDetector.get_active_session_info(self.mock_claude_dir)
        self.assertTrue(info_with_cookies["is_signed_in"])
    def test_switch_account_creates_rolling_backup(self):
        """Verify ProfileManager.switch_account creates a rolling backup of the source account."""
        from unittest.mock import patch
        from core.profile_manager import ProfileManager

        pm = ProfileManager()
        pm.config = self.config

        # Setup active session with cookies
        net_dir = self.mock_claude_dir / "Network"
        net_dir.mkdir(parents=True, exist_ok=True)
        (net_dir / "Cookies").write_bytes(b"active_cookies")
        (self.mock_claude_dir / "config.json").write_text('{"windowSizeWasSignedIn": true, "lastKnownAccountUuid": "u_active"}', encoding="utf-8")

        # Setup target profile
        target_dir = self.config.profiles_dir / "account_target"
        target_net = target_dir / "Network"
        target_net.mkdir(parents=True, exist_ok=True)
        (target_net / "Cookies").write_bytes(b"target_cookies")
        (target_dir / "config.json").write_text('{"lastKnownAccountUuid": "u_target"}', encoding="utf-8")

        self.config.save_accounts({
            "active_account_id": "account_src",
            "accounts": {
                "account_src": {"name": "Source Account", "account_uuid": "u_active"},
                "account_target": {"name": "Target Account", "account_uuid": "u_target"}
            }
        })

        with patch.object(pm.process_manager, "close_claude"), \
             patch.object(pm.process_manager, "launch_claude", return_value=True), \
             patch.object(pm.detector, "is_claude_running", return_value=False), \
             patch.object(self.config, "get_claude_profile_dir", return_value=self.mock_claude_dir):
            success = pm.switch_account("account_target", restart_claude=False)
            self.assertTrue(success)

            # Rolling backup must exist for source account
            rolling_backup_cookies = self.config.backups_dir / "backup_account_src" / "Network" / "Cookies"
            self.assertTrue(rolling_backup_cookies.exists())
            self.assertEqual(rolling_backup_cookies.read_bytes(), b"active_cookies")


if __name__ == "__main__":
    unittest.main()


