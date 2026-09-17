"""Profile manager for safe snapshots, zero-bloat profile swapping, and safety backups."""

import os
import time
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
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

    def copy_session_payload(self, src_dir: Path, dest_dir: Path) -> int:
        """
        Copy only auth and session-critical files (~10-15 MB).
        Explicitly skips multi-gigabyte VM bundles, binaries, and heavy caches.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied_count = 0

        for item in src_dir.iterdir():
            if item.name in EXCLUDED_PROFILE_ITEMS:
                continue

            dest_item = dest_dir / item.name
            try:
                if item.is_dir():
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(item, dest_item, ignore=shutil.ignore_patterns(*EXCLUDED_PROFILE_ITEMS))
                else:
                    shutil.copy2(item, dest_item)
                copied_count += 1
            except Exception as e:
                logger.warning(f"Error copying {item.name}: {e}")

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
        profile_dir = self.config.profiles_dir / active_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        self.copy_session_payload(claude_dir, profile_dir)

        session_info = self.detector.get_active_session_info(claude_dir)
        acc = accounts["accounts"][active_id]
        acc["last_active"] = datetime.now().isoformat()
        if session_info.get("account_uuid"):
            acc["account_uuid"] = session_info["account_uuid"]
        if session_info.get("org_uuids"):
            acc["org_uuids"] = session_info["org_uuids"]

        self.config.save_accounts(accounts)
        return True

    def switch_account(
        self,
        target_account_id: str,
        carry_over_session_ids: Optional[List[str]] = None,
        restart_claude: bool = True
    ) -> bool:
        """
        Switch from current active account to target account.
        Selectively carries over chosen sessions if requested.
        Preserves 12 GB vm_bundles and binaries untouched.
        """
        accounts = self.config.load_accounts()
        if target_account_id not in accounts["accounts"]:
            raise ValueError(f"Target account not found: {target_account_id}")

        source_acc_id = accounts.get("active_account_id")
        claude_dir = self.config.get_claude_profile_dir()
        target_profile_dir = self.config.profiles_dir / target_account_id

        if not target_profile_dir.exists():
            raise FileNotFoundError(f"Target profile directory missing: {target_profile_dir}")

        was_running = self.detector.is_claude_running()

        # Step 1: Transfer specific selected sessions if requested
        if carry_over_session_ids and source_acc_id:
            src_acc = accounts["accounts"].get(source_acc_id, {})
            dst_acc = accounts["accounts"].get(target_account_id, {})
            src_uuid = src_acc.get("account_uuid")
            dst_uuid = dst_acc.get("account_uuid")
            if src_uuid and dst_uuid:
                logger.info(f"Carrying over {len(carry_over_session_ids)} sessions from {src_uuid} to {dst_uuid}")
                self.session_manager.transfer_selected_sessions(
                    carry_over_session_ids, src_uuid, dst_uuid, claude_dir=claude_dir
                )

        # Step 2: Gracefully close Claude Desktop to release file locks
        if was_running:
            self.process_manager.close_claude()
            time.sleep(0.5)

        # Step 3: Save any updated session state of the current account
        if source_acc_id and source_acc_id in accounts["accounts"]:
            src_profile_dir = self.config.profiles_dir / source_acc_id
            self.copy_session_payload(claude_dir, src_profile_dir)

        # Step 4: Clean current session files from active directory (keeping vm_bundles / claude-code intact)
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

        # Step 6: Update registry
        accounts["active_account_id"] = target_account_id
        accounts["accounts"][target_account_id]["last_active"] = datetime.now().isoformat()
        self.config.save_accounts(accounts)

        # Step 7: Re-launch Claude Desktop
        if restart_claude:
            self.process_manager.launch_claude()

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

        # Step 1: Save current active account
        self.save_current_profile()

        # Generate new account ID
        new_id = f"account_{int(time.time())}"
        new_profile_dir = self.config.profiles_dir / new_id
        new_profile_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Close Claude Desktop
        self.process_manager.close_claude()
        time.sleep(0.5)

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
