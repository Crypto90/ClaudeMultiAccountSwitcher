"""Detection of Claude Desktop processes, installation paths, and session state."""

import os
import json
import logging
import psutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.config import config, SESSION_ITEMS

logger = logging.getLogger("ClaudeSwitcher.Detector")


class ClaudeDetector:
    """Detects Claude Desktop process state, file locks, and active login session."""

    @staticmethod
    def is_claude_running() -> bool:
        """Check if any Claude Desktop process is actively running."""
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                name = (proc.info["name"] or "").lower()
                exe = (proc.info["exe"] or "").lower()
                if "claude.exe" in name and "claude-code" not in exe:
                    return True
                # Also check WindowsApps claude
                if "claude" in name and "windowsapps" in exe:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    @staticmethod
    def get_claude_processes() -> List[Dict[str, Any]]:
        """Get detailed information about running Claude processes."""
        processes = []
        for proc in psutil.process_iter(["pid", "name", "exe", "create_time", "memory_info"]):
            try:
                name = (proc.info["name"] or "").lower()
                exe = (proc.info["exe"] or "").lower()
                if "claude.exe" in name and ("windowsapps" in exe or "appdata" in exe):
                    mem_mb = 0
                    if proc.info["memory_info"]:
                        mem_mb = round(proc.info["memory_info"].rss / (1024 * 1024), 1)
                    processes.append({
                        "pid": proc.info["pid"],
                        "name": proc.info["name"],
                        "exe": proc.info["exe"],
                        "create_time": proc.info["create_time"],
                        "memory_mb": mem_mb
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    @staticmethod
    def is_cookies_locked(claude_dir: Optional[Path] = None) -> bool:
        """Check if SQLite Cookies file is currently locked by a running instance."""
        target_dir = claude_dir or config.get_claude_profile_dir()
        cookies_file = target_dir / "Network" / "Cookies"
        if not cookies_file.exists():
            return False

        try:
            # Try to open the file in append/exclusive mode
            with open(cookies_file, "r+b"):
                pass
            return False
        except (IOError, PermissionError, OSError):
            return True

    @staticmethod
    def get_active_session_info(claude_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Read and parse current Claude session metadata safely without modifying files."""
        target_dir = claude_dir or config.get_claude_profile_dir()
        config_path = target_dir / "config.json"
        
        info = {
            "exists": target_dir.exists(),
            "profile_path": str(target_dir),
            "is_signed_in": False,
            "account_uuid": None,
            "has_tokens": False,
            "locale": "en-US",
            "version": None,
            "org_uuids": []
        }

        if not config_path.exists():
            return info

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            info["account_uuid"] = cfg.get("lastKnownAccountUuid")
            info["is_signed_in"] = bool(cfg.get("windowSizeWasSignedIn", False))
            info["locale"] = cfg.get("locale", "en-US")
            info["version"] = cfg.get("updaterLastSeenVersion")
            info["has_tokens"] = "oauth:tokenCache" in cfg or "oauth:tokenCacheV2" in cfg

            # Discover org UUIDs from allowlist keys or claude-code-sessions
            org_uuids = set()
            for k in cfg.keys():
                if k.startswith("dxt:allowlistEnabled:"):
                    org_uuids.add(k.split(":")[-1])
            
            # Also check session directory folders
            if info["account_uuid"]:
                acc_sess_dir = target_dir / "claude-code-sessions" / info["account_uuid"]
                if acc_sess_dir.exists():
                    for item in acc_sess_dir.iterdir():
                        if item.is_dir():
                            org_uuids.add(item.name)

            info["org_uuids"] = list(org_uuids)

        except Exception as e:
            logger.error(f"Error reading Claude config.json: {e}")

        return info


detector = ClaudeDetector()
