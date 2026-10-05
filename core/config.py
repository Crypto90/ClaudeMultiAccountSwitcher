"""Configuration, path resolution, and settings management for Claude Switcher."""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ClaudeSwitcher.Config")

# Default excluded directories and files to keep profile sizes ~10-15 MB instead of 12+ GB
EXCLUDED_PROFILE_ITEMS = {
    # Heavy binaries & VM images
    "vm_bundles",          # 11+ GB Coworker VM image (stays shared in Claude active dir)
    "claude-code",         # 450 MB binary distribution
    "claude-code-vm",      # 210 MB VM support
    # Chromium GPU and compiled script caches
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    # Volatile / diagnostics
    "Crashpad",
    "logs",
    "lockfile",
    "blob_storage",
    # Persistent session databases (namespaced by account UUID; preserved in-place across switches)
    "claude-code-sessions",
    "local-agent-mode-sessions",
    # Shared browser extension native messaging host daemon
    "ChromeNativeHost"
}

# Core session items that MUST be preserved for authentication and session continuity
SESSION_ITEMS = [
    "config.json",
    "Local State",
    "Network",
    "Local Storage",
    "Session Storage",
    "IndexedDB",
    "Preferences",
    "ant-device-registry.json",
    "ant-did",
    "buddy-tokens.json",
    "ccd-ids.json",
    "spaces-present",
    "window-state.json",
    "plan-usage-history.json",
    "declarative_performance_observer.db",
    "declarative_performance_observer.db-journal",
    "DIPS",
    "DIPS-wal",
    "fcache",
    "WebStorage",
    "shared_proto_db",
    "claude_desktop_config.json"
]


class AppConfig:
    """Manages application paths, account registry, and persistent settings."""

    def __init__(self, custom_app_data_dir: Optional[str] = None):
        self._user_home = Path.home()
        self._local_appdata = Path(os.environ.get("LOCALAPPDATA", str(self._user_home / "AppData" / "Local")))
        self._roaming_appdata = Path(os.environ.get("APPDATA", str(self._user_home / "AppData" / "Roaming")))

        # App storage directory
        if custom_app_data_dir:
            self.app_dir = Path(custom_app_data_dir)
        else:
            self.app_dir = self._roaming_appdata / "ClaudeSwitcher"

        self.profiles_dir = self.app_dir / "profiles"
        self.backups_dir = self.app_dir / "backups"
        self.initial_backup_dir = self.backups_dir / "initial_session"
        self.accounts_file = self.app_dir / "accounts.json"
        self.settings_file = self.app_dir / "settings.json"

        # Claude installation & profile paths
        self.msix_claude_dir = (
            self._local_appdata / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude"
        )
        self.standard_claude_dir = self._roaming_appdata / "Claude"
        self.claude_home_dir = self._user_home / ".claude"

        # Ensure directory structure exists
        self._init_directories()

    def _init_directories(self) -> None:
        """Create necessary directories if they do not exist."""
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def get_claude_profile_dir(self) -> Path:
        """Return the active Claude profile directory."""
        if self.msix_claude_dir.exists():
            return self.msix_claude_dir
        if self.standard_claude_dir.exists():
            return self.standard_claude_dir
        # Default to MSIX path as standard for Windows Store/Anthropic package
        return self.msix_claude_dir

    def get_claude_sessions_dir(self) -> Path:
        """Return the directory where claude-code-sessions are kept."""
        return self.get_claude_profile_dir() / "claude-code-sessions"

    def load_settings(self) -> Dict[str, Any]:
        """Load user settings or return defaults."""
        defaults = {
            "share_mcp_config": True,
            "minimize_to_tray": True,
            "start_with_windows": False,
            "auto_backup_on_switch": True,
            "prompt_session_carryover": True,
            "dark_theme": True,
        }
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception as e:
                logger.error(f"Failed to read settings: {e}")
        return defaults

    def save_settings(self, settings: Dict[str, Any]) -> None:
        """Save user settings atomically."""
        tmp_file = self.settings_file.with_suffix(".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            if tmp_file.exists():
                tmp_file.replace(self.settings_file)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def load_accounts(self) -> Dict[str, Any]:
        """Load the accounts registry."""
        default_registry = {
            "active_account_id": None,
            "initial_backup_created": False,
            "accounts": {}
        }
        if self.accounts_file.exists():
            try:
                with open(self.accounts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_registry.update(data)
            except Exception as e:
                logger.error(f"Failed to read accounts: {e}")
        return default_registry

    def save_accounts(self, registry: Dict[str, Any]) -> None:
        """Save the accounts registry atomically."""
        tmp_file = self.accounts_file.with_suffix(".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
            if tmp_file.exists():
                tmp_file.replace(self.accounts_file)
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")


# Singleton instance
config = AppConfig()
