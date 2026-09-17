"""Selective session management and cross-account session transfer."""

import os
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.config import config

logger = logging.getLogger("ClaudeSwitcher.SessionManager")


class SessionManager:
    """Discovers, parses, and selectively transfers Claude Cowork / Agent sessions across accounts."""

    @staticmethod
    def _format_timestamp(ts_ms: Optional[int]) -> str:
        """Format millisecond timestamp into a human-readable string."""
        if not ts_ms:
            return "Unknown"
        try:
            dt = datetime.fromtimestamp(ts_ms / 1000.0)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Invalid Date"

    @classmethod
    def get_sessions_for_account(cls, account_uuid: str, claude_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        """List all valid sessions belonging to a specific account UUID."""
        base_dir = claude_dir or config.get_claude_profile_dir()
        sessions_root = base_dir / "claude-code-sessions" / account_uuid
        sessions = []

        if not sessions_root.exists():
            return sessions

        for org_dir in sessions_root.iterdir():
            if not org_dir.is_dir():
                continue

            for session_file in org_dir.glob("local_*.json"):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    session_id = data.get("sessionId", session_file.stem)
                    title = data.get("title") or "Untitled Session"
                    cwd = data.get("cwd") or data.get("originCwd") or "Unknown Directory"
                    created_at = data.get("createdAt", 0)
                    last_activity = data.get("lastActivityAt") or created_at
                    model = data.get("model", "Default Model")
                    turns_val = data.get("completedTurns", 0)
                    turns = turns_val if isinstance(turns_val, int) else len(turns_val)
                    cli_id = data.get("cliSessionId")

                    # Extract concise project name from cwd
                    project_name = Path(cwd).name if cwd != "Unknown Directory" else "General"

                    sessions.append({
                        "session_id": session_id,
                        "cli_session_id": cli_id,
                        "title": title,
                        "project_name": project_name,
                        "cwd": cwd,
                        "model": model,
                        "turns": turns,
                        "created_at": created_at,
                        "last_activity": last_activity,
                        "last_activity_str": cls._format_timestamp(last_activity),
                        "account_uuid": account_uuid,
                        "org_uuid": org_dir.name,
                        "file_path": str(session_file)
                    })
                except Exception as e:
                    logger.debug(f"Failed to read session file {session_file}: {e}")

        # Sort by most recently active first
        sessions.sort(key=lambda s: s.get("last_activity", 0), reverse=True)
        return sessions

    @classmethod
    def get_all_sessions(cls, claude_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        """List all sessions across all accounts present in claude-code-sessions."""
        base_dir = claude_dir or config.get_claude_profile_dir()
        sessions_root = base_dir / "claude-code-sessions"
        all_sessions = []

        if not sessions_root.exists():
            return all_sessions

        for acc_dir in sessions_root.iterdir():
            if acc_dir.is_dir():
                all_sessions.extend(cls.get_sessions_for_account(acc_dir.name, claude_dir))

        all_sessions.sort(key=lambda s: s.get("last_activity", 0), reverse=True)
        return all_sessions

    @classmethod
    def get_most_recent_session(cls, account_uuid: str, claude_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Retrieve the single most recent session for an account (useful for quick carryover)."""
        sessions = cls.get_sessions_for_account(account_uuid, claude_dir)
        return sessions[0] if sessions else None

    @classmethod
    def transfer_selected_sessions(
        cls,
        session_ids: List[str],
        from_account_uuid: str,
        to_account_uuid: str,
        to_org_uuid: Optional[str] = None,
        move: bool = False,
        claude_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Transfer specifically selected session JSON files from one account UUID to another.
        Preserves the exact session state so the destination account can immediately resume it.
        """
        base_dir = claude_dir or config.get_claude_profile_dir()
        source_account_dir = base_dir / "claude-code-sessions" / from_account_uuid
        target_account_dir = base_dir / "claude-code-sessions" / to_account_uuid

        result = {
            "transferred_count": 0,
            "transferred_sessions": [],
            "errors": []
        }

        if not source_account_dir.exists():
            result["errors"].append(f"Source account sessions directory not found: {from_account_uuid}")
            return result

        # Determine target org UUID
        target_org = to_org_uuid
        if not target_org:
            if target_account_dir.exists():
                existing_orgs = [d.name for d in target_account_dir.iterdir() if d.is_dir()]
                if existing_orgs:
                    target_org = existing_orgs[0]

        # Scan source sessions matching requested IDs
        all_source_sessions = cls.get_sessions_for_account(from_account_uuid, claude_dir)
        sessions_to_copy = [s for s in all_source_sessions if s["session_id"] in session_ids]

        if not sessions_to_copy:
            result["errors"].append("No matching sessions found to transfer.")
            return result

        for sess in sessions_to_copy:
            source_file = Path(sess["file_path"])
            dest_org = target_org or sess["org_uuid"]
            dest_dir = target_account_dir / dest_org
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / source_file.name

            try:
                if move:
                    shutil.move(str(source_file), str(dest_file))
                else:
                    shutil.copy2(str(source_file), str(dest_file))

                result["transferred_count"] += 1
                result["transferred_sessions"].append(sess["title"])
                logger.info(f"Successfully transferred session '{sess['title']}' to {to_account_uuid}/{dest_org}")
            except Exception as e:
                err_msg = f"Failed to transfer session {sess['title']}: {e}"
                logger.error(err_msg)
                result["errors"].append(err_msg)

        return result

    @classmethod
    def delete_session(cls, session: Dict[str, Any], claude_dir: Optional[Path] = None) -> bool:
        """
        Delete a session file from disk.
        Safely verifies the file is inside claude-code-sessions to prevent accidental deletions.
        """
        file_path = session.get("file_path")
        base_dir = (claude_dir or config.get_claude_profile_dir()).resolve()
        sessions_root = (base_dir / "claude-code-sessions").resolve()

        if not file_path and "session_id" in session and "account_uuid" in session:
            # Fallback lookup
            for s in cls.get_sessions_for_account(session["account_uuid"], claude_dir):
                if s["session_id"] == session["session_id"]:
                    file_path = s["file_path"]
                    break

        if not file_path:
            logger.error("No file_path provided or found for session deletion.")
            return False

        path = Path(file_path).resolve()

        # Security check: ensure path is inside sessions_root and is a valid session JSON file
        try:
            path.relative_to(sessions_root)
        except ValueError:
            logger.error(f"Refusing to delete file outside claude-code-sessions: {path}")
            return False

        if not path.is_file() or not path.name.startswith("local_") or path.suffix != ".json":
            logger.error(f"Refusing to delete non-session file: {path}")
            return False

        try:
            path.unlink(missing_ok=True)
            logger.info(f"Deleted session file: {path}")

            # Check if parent org dir is now empty; if so, remove it cleanly
            parent_dir = path.parent
            if parent_dir.exists() and not any(parent_dir.iterdir()):
                try:
                    parent_dir.rmdir()
                    logger.debug(f"Removed empty org directory: {parent_dir}")
                except Exception:
                    pass

            return True
        except Exception as e:
            logger.error(f"Failed to delete session file {path}: {e}")
            return False

    @classmethod
    def delete_sessions(cls, sessions: List[Dict[str, Any]], claude_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Batch delete a list of sessions.
        Returns dict with 'deleted_count' and 'errors'.
        """
        result = {
            "deleted_count": 0,
            "errors": []
        }
        for sess in sessions:
            title = sess.get("title", "Untitled")
            success = cls.delete_session(sess, claude_dir)
            if success:
                result["deleted_count"] += 1
            else:
                result["errors"].append(f"Failed to delete '{title}'")
        return result


session_manager = SessionManager()
