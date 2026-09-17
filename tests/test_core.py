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


if __name__ == "__main__":
    unittest.main()
