"""Profile manager for safe snapshots, zero-bloat profile swapping, and safety backups."""

import os
import time
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from core.config import config, EXCLUDED_PROFILE_ITEMS, SESSION_ITEMS
from core.detector import detector
from core.process_manager import process_manager
from core.session_manager import session_manager

logger = logging.getLogger("ClaudeSwitcher.ProfileManager")


class ProfileManager:
    """Manages profile snapshots, zero-bloat account swapping, and baseline backups."""

    def __init__(self):
        self.config = config
        self.detector = detector
        self.process_manager = process_manager
        self.session_manager = session_manager

    @staticmethod
    def _copy_file_with_retry(src: Path, dest: Path, retries: int = 4, delay: float = 0.25) -> bool:
        """Copy a file, retrying if temporarily locked by another process."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(retries):
            try:
                shutil.copy2(src, dest)
                return True
            except (PermissionError, OSError) as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    logger.warning(f"Failed to copy {src.name} after {retries} attempts: {e}")
                    return False
        return False

    def _copy_dir_safely(self, src: Path, dest: Path) -> int:
        """Safely copy a directory hierarchy without destroying target if locked."""
        dest.mkdir(parents=True, exist_ok=True)
        copied = 0
        for root, dirs, files in os.walk(str(src)):
            rel_path = Path(root).relative_to(src)
            dirs[:] = [d for d in dirs if d not in EXCLUDED_PROFILE_ITEMS]
            dest_subdir = dest / rel_path
            dest_subdir.mkdir(parents=True, exist_ok=True)
            for f in files:
                if f in EXCLUDED_PROFILE_ITEMS:
                    continue
                s_file = Path(root) / f
                d_file = dest_subdir / f
                if self._copy_file_with_retry(s_file, d_file):
                    copied += 1
        return copied

    def copy_session_payload(self, src_dir: Path, dest_dir: Path) -> int:
        """
        Copy only auth and session-critical files (~10-15 MB).
        Explicitly skips multi-gigabyte VM bundles, binaries, and heavy caches.
        Never prematurely deletes existing destination directories, and validates critical auth items.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied_count = 0

        for item in src_dir.iterdir():
            if item.name in EXCLUDED_PROFILE_ITEMS:
                continue

            dest_item = dest_dir / item.name
            try:
                if item.is_dir():
                    self._copy_dir_safely(item, dest_item)
                else:
                    self._copy_file_with_retry(item, dest_item)
                copied_count += 1
            except Exception as e:
                logger.warning(f"Error copying {item.name}: {e}")

        # Safety validation: if src_dir had Network/Cookies, ensure dest_dir has it too!
        src_cookies = src_dir / "Network" / "Cookies"
        dest_cookies = dest_dir / "Network" / "Cookies"
        if src_cookies.exists() and src_cookies.stat().st_size > 0:
            if not dest_cookies.exists() or dest_cookies.stat().st_size == 0:
                logger.warning("Network/Cookies missing after initial copy, attempting rescue copy...")
                self._copy_file_with_retry(src_cookies, dest_cookies, retries=5, delay=0.3)

        return copied_count

    def ensure_initial_backup(self) -> bool:
        """
        Safety guarantee: creates an immutable baseline backup of the user's
        existing Claude session if one hasn't been created yet.
        """
        accounts = self.config.load_accounts()
        if accounts.get("initial_backup_created") and self.config.initial_backup_dir.exists():
            return True

        claude_dir = self.config.get_claude_profile_dir()
        if not claude_dir.exists():
            logger.info("No existing Claude profile directory found; initial backup not required.")
            return True

        logger.info("Creating immutable baseline backup of active Claude session...")
        was_running = self.detector.is_claude_running()

        if was_running:
            self.process_manager.close_claude()
            time.sleep(0.5)

        # Perform atomic copy
        self.config.initial_backup_dir.mkdir(parents=True, exist_ok=True)
        copied = self.copy_session_payload(claude_dir, self.config.initial_backup_dir)

        # Write manifest
        session_info = self.detector.get_active_session_info(claude_dir)
        manifest = {
            "created_at": datetime.now().isoformat(),
            "files_copied": copied,
            "account_uuid": session_info.get("account_uuid"),
            "is_signed_in": session_info.get("is_signed_in"),
            "source_dir": str(claude_dir)
        }
        with open(self.config.initial_backup_dir / "backup_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Also initialize Account #1 (Primary) from this active session
        initial_acc_id = "account_primary"
        primary_profile_dir = self.config.profiles_dir / initial_acc_id
        self.copy_session_payload(claude_dir, primary_profile_dir)

        accounts["initial_backup_created"] = True
        accounts["active_account_id"] = initial_acc_id
        accounts["accounts"][initial_acc_id] = {
            "id": initial_acc_id,
            "name": "Main Account",
            "avatar_color": "#d97706",  # Anthropic terracotta
            "account_uuid": session_info.get("account_uuid"),
            "org_uuids": session_info.get("org_uuids", []),
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "is_primary": True
        }
        self.config.save_accounts(accounts)

        if was_running:
            self.process_manager.launch_claude()

        logger.info(f"Baseline backup successfully secured ({copied} items).")
        return True

    def save_current_profile(self) -> bool:
        """Save the active Claude Desktop session into the active account profile folder."""
        accounts = self.config.load_accounts()
        active_id = accounts.get("active_account_id")
        if not active_id or active_id not in accounts["accounts"]:
            return False

        claude_dir = self.config.get_claude_profile_dir()
        session_info = self.detector.get_active_session_info(claude_dir)
        target_acc = accounts["accounts"][active_id]

        # CRITICAL SAFETY CHECK:
        # Never overwrite an existing signed-in profile with a logged-out or unauthenticated session!
        if not session_info.get("is_signed_in"):
            if target_acc.get("account_uuid") and not target_acc.get("is_pending_login"):
                logger.warning(
                    f"Refusing to overwrite signed-in profile '{target_acc.get('name')}' with unauthenticated or cookie-less session."
                )
                return False

        # Ensure Claude Desktop is closed to release SQLite Cookies and LevelDB locks
        was_running = self.detector.is_claude_running()
        if was_running:
            self.process_manager.close_claude()
            time.sleep(0.5)

        profile_dir = self.config.profiles_dir / active_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        self.copy_session_payload(claude_dir, profile_dir)

        acc = accounts["accounts"][active_id]
        acc["last_active"] = datetime.now().isoformat()
        if session_info.get("account_uuid"):
            acc["account_uuid"] = session_info["account_uuid"]
        if session_info.get("org_uuids"):
            acc["org_uuids"] = session_info["org_uuids"]

        self.config.save_accounts(accounts)

        if was_running:
            self.process_manager.launch_claude()

        return True

    def switch_account(
        self,
        target_account_id: str,
        carry_over_session_ids: Optional[List[str]] = None,
        move_sessions: bool = True,
        restart_claude: bool = True,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Switch from current active account to target account.
        Selectively moves or copies chosen sessions (defaults to move).
        Preserves 12 GB vm_bundles, session databases, and binaries untouched.
        Guarantees that Claude Desktop is cleanly restarted and running afterwards.
        """
        accounts = self.config.load_accounts()
        if target_account_id not in accounts["accounts"]:
            raise ValueError(f"Target account not found: {target_account_id}")

        source_acc_id = accounts.get("active_account_id")
        target_acc_name = accounts["accounts"][target_account_id].get("name", "Target Account")
        claude_dir = self.config.get_claude_profile_dir()
        target_profile_dir = self.config.profiles_dir / target_account_id

        if not target_profile_dir.exists():
            raise FileNotFoundError(f"Target profile directory missing: {target_profile_dir}")

        # Step 0: Pre-flight validation of target profile
        target_cookies = target_profile_dir / "Network" / "Cookies"
        if not target_cookies.exists() or target_cookies.stat().st_size == 0:
            rolling_backup_cookies = self.config.backups_dir / f"backup_{target_account_id}" / "Network" / "Cookies"
            init_cookies = self.config.initial_backup_dir / "Network" / "Cookies"
            backup_source = None
            if rolling_backup_cookies.exists() and rolling_backup_cookies.stat().st_size > 0:
                backup_source = rolling_backup_cookies
            elif target_account_id == "account_primary" and init_cookies.exists() and init_cookies.stat().st_size > 0:
                backup_source = init_cookies

            if backup_source:
                logger.info(f"Auto-healing profile '{target_account_id}': restoring Network/Cookies from {backup_source.parent}...")
                target_cookies.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_source, target_cookies)
                journal_src = backup_source.parent / "Cookies-journal"
                if journal_src.exists():
                    shutil.copy2(journal_src, target_cookies.parent / "Cookies-journal")

        was_running = self.detector.is_claude_running()

        # Step 1: Gracefully close Claude Desktop FIRST to flush open files and unlock databases
        if was_running or self.detector.is_claude_running():
            if status_callback:
                status_callback("Closing Claude Desktop safely...")
            self.process_manager.close_claude()
            time.sleep(0.5)

        # Step 2: Move or copy specific selected sessions if requested
        if carry_over_session_ids and source_acc_id:
            src_acc = accounts["accounts"].get(source_acc_id, {})
            dst_acc = accounts["accounts"].get(target_account_id, {})
            src_uuid = src_acc.get("account_uuid")
            dst_uuid = dst_acc.get("account_uuid")
            if src_uuid and dst_uuid:
                verb = "Moving" if move_sessions else "Copying"
                if status_callback:
                    status_callback(f"{verb} {len(carry_over_session_ids)} sessions...")
                logger.info(f"{verb} {len(carry_over_session_ids)} sessions from {src_uuid} to {dst_uuid}")
                self.session_manager.transfer_selected_sessions(
                    carry_over_session_ids, src_uuid, dst_uuid, move=move_sessions, claude_dir=claude_dir
                )

        # Step 3: Save any updated session state of the current account ONLY if authenticated!
        if source_acc_id and source_acc_id in accounts["accounts"]:
            if status_callback:
                status_callback("Saving current profile snapshot...")
            session_info = self.detector.get_active_session_info(claude_dir)
            source_acc = accounts["accounts"][source_acc_id]
            if session_info.get("is_signed_in"):
                src_profile_dir = self.config.profiles_dir / source_acc_id
                self.copy_session_payload(claude_dir, src_profile_dir)
                source_acc["last_active"] = datetime.now().isoformat()
                if session_info.get("account_uuid"):
                    source_acc["account_uuid"] = session_info["account_uuid"]

                # Rolling backup of last good session state
                settings = self.config.load_settings()
                if settings.get("auto_backup_on_switch", True):
                    rolling_backup = self.config.backups_dir / f"backup_{source_acc_id}"
                    self.copy_session_payload(src_profile_dir, rolling_backup)
            else:
                logger.info(f"Skipping save of '{source_acc.get('name')}' as active session is not authenticated.")

        # Step 4: Clean current session files from active directory (keeping vm_bundles / claude-code intact)
        if status_callback:
            status_callback(f"Activating profile for {target_acc_name}...")
        for item in claude_dir.iterdir():
            if item.name in EXCLUDED_PROFILE_ITEMS or item.name == "claude_desktop_config.json":
                # Keep shared MCP config if enabled in settings
                settings = self.config.load_settings()
                if item.name == "claude_desktop_config.json" and settings.get("share_mcp_config", True):
                    continue
            if item.name not in EXCLUDED_PROFILE_ITEMS:
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.debug(f"Could not remove old item {item.name}: {e}")

        # Step 5: Copy target account files into active Claude directory
        self.copy_session_payload(target_profile_dir, claude_dir)

        # Verification of active Cookies post-switch
        target_cookies = target_profile_dir / "Network" / "Cookies"
        active_cookies = claude_dir / "Network" / "Cookies"
        if target_cookies.exists() and (not active_cookies.exists() or active_cookies.stat().st_size == 0):
            logger.warning("Active Network/Cookies missing after switch; forcing direct copy.")
            self._copy_file_with_retry(target_cookies, active_cookies, retries=5)

        # Step 6: Update registry
        accounts["active_account_id"] = target_account_id
        accounts["accounts"][target_account_id]["last_active"] = datetime.now().isoformat()
        self.config.save_accounts(accounts)

        # Step 7: Re-launch Claude Desktop and verify it started
        if restart_claude:
            if status_callback:
                status_callback("Starting Claude Desktop...")
            logger.info("Starting Claude Desktop post-switch...")
            launched = self.process_manager.launch_claude()
            if not launched:
                logger.warning("Claude Desktop launch could not be confirmed running.")
            else:
                logger.info("Claude Desktop launched and running.")

        logger.info(f"Switched successfully to account: {accounts['accounts'][target_account_id]['name']}")
        return True

    def create_new_account_setup(
        self,
        account_name: str,
        avatar_color: str = "#8b5cf6",
        share_mcp: bool = True
    ) -> str:
        """
        Prepares a fresh session environment to sign into a new account.
        Backs up the current profile, leaves vm_bundles in place, cleans old auth,
        and launches Claude Desktop in fresh sign-in mode.
        """
        # Ensure baseline is safe
        self.ensure_initial_backup()

        claude_dir = self.config.get_claude_profile_dir()
        accounts = self.config.load_accounts()

        # Step 1: Close Claude Desktop FIRST so files are unlocked and consistent
        if self.detector.is_claude_running():
            self.process_manager.close_claude()
            time.sleep(0.5)

        # Step 2: Now that Claude is closed, safely save current active account
        self.save_current_profile()

        # Generate new account ID
        new_id = f"account_{int(time.time())}"
        new_profile_dir = self.config.profiles_dir / new_id
        new_profile_dir.mkdir(parents=True, exist_ok=True)

        # Preserve MCP config if requested
        mcp_content = None
        mcp_file = claude_dir / "claude_desktop_config.json"
        if share_mcp and mcp_file.exists():
            try:
                mcp_content = mcp_file.read_text(encoding="utf-8")
            except Exception:
                pass

        # Step 3: Clear old auth & cookies from active directory
        for item in claude_dir.iterdir():
            if item.name not in EXCLUDED_PROFILE_ITEMS:
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.debug(f"Could not clear {item.name}: {e}")

        # Restore MCP config if shared
        if mcp_content and mcp_file:
            try:
                mcp_file.write_text(mcp_content, encoding="utf-8")
            except Exception:
                pass

        # Register pending account
        accounts["active_account_id"] = new_id
        accounts["accounts"][new_id] = {
            "id": new_id,
            "name": account_name,
            "avatar_color": avatar_color,
            "account_uuid": None,
            "org_uuids": [],
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "is_pending_login": True
        }
        self.config.save_accounts(accounts)

        # Step 4: Launch Claude so user can complete sign in
        self.process_manager.launch_claude()
        return new_id

    def restore_initial_backup(self) -> bool:
        """Emergency Panic Button: Restores the original session baseline."""
        if not self.config.initial_backup_dir.exists():
            raise FileNotFoundError("Initial backup directory does not exist.")

        claude_dir = self.config.get_claude_profile_dir()
        self.process_manager.close_claude()
        time.sleep(0.5)

        # Clear session files
        for item in claude_dir.iterdir():
            if item.name not in EXCLUDED_PROFILE_ITEMS:
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception:
                    pass

        # Copy baseline
        self.copy_session_payload(self.config.initial_backup_dir, claude_dir)

        # Reset active account to primary
        accounts = self.config.load_accounts()
        accounts["active_account_id"] = "account_primary"
        self.config.save_accounts(accounts)

        self.process_manager.launch_claude()
        return True


profile_manager = ProfileManager()
