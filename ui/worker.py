"""Background workers to run Claude process management and profile swapping without freezing the UI."""

import logging
from typing import Optional, List
from PyQt6.QtCore import QThread, pyqtSignal

from core.profile_manager import profile_manager
from core.process_manager import process_manager

logger = logging.getLogger("ClaudeSwitcher.Worker")


class SwitchAccountWorker(QThread):
    """Worker thread that executes account switching in the background so the UI never freezes."""

    status_changed = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # (success, message_or_error)

    def __init__(
        self,
        target_account_id: str,
        carry_over_session_ids: Optional[List[str]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.target_account_id = target_account_id
        self.carry_over_session_ids = carry_over_session_ids

    def run(self):
        try:
            self.status_changed.emit("Closing Claude Desktop safely...")
            # Execute switch in background thread
            success = profile_manager.switch_account(
                self.target_account_id,
                carry_over_session_ids=self.carry_over_session_ids,
                restart_claude=True
            )
            if success:
                self.finished.emit(True, "Account switched successfully!")
            else:
                self.finished.emit(False, "Failed to switch account.")
        except Exception as e:
            logger.error(f"SwitchAccountWorker exception: {e}")
            self.finished.emit(False, str(e))


class RestartClaudeWorker(QThread):
    """Worker thread to restart Claude Desktop asynchronously."""

    status_changed = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            self.status_changed.emit("Closing Claude Desktop...")
            process_manager.restart_claude()
            self.finished.emit(True, "Claude Desktop restarted.")
        except Exception as e:
            logger.error(f"RestartClaudeWorker exception: {e}")
            self.finished.emit(False, str(e))


class CreateAccountWorker(QThread):
    """Worker thread to prepare fresh account environment asynchronously."""

    status_changed = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # (success, new_id, message_or_error)

    def __init__(self, account_name: str, avatar_color: str, share_mcp: bool, parent=None):
        super().__init__(parent)
        self.account_name = account_name
        self.avatar_color = avatar_color
        self.share_mcp = share_mcp

    def run(self):
        try:
            self.status_changed.emit("Securing current session and closing Claude...")
            new_id = profile_manager.create_new_account_setup(
                self.account_name,
                avatar_color=self.avatar_color,
                share_mcp=self.share_mcp
            )
            self.finished.emit(True, new_id, "Ready for sign-in.")
        except Exception as e:
            logger.error(f"CreateAccountWorker exception: {e}")
            self.finished.emit(False, "", str(e))


class StatusMonitorThread(QThread):
    """Background daemon thread to monitor Claude process state without touching the GUI thread."""

    status_updated = pyqtSignal(bool, int)  # (is_running, count)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        from core.detector import detector
        import time

        last_state = None
        last_count = -1
        while self._running:
            try:
                count = detector.get_claude_process_count()
                is_running = count > 0
                if is_running != last_state or count != last_count:
                    last_state = is_running
                    last_count = count
                    self.status_updated.emit(is_running, count)
            except Exception:
                pass

            # Sleep in background thread for 3.5s
            for _ in range(35):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait(1000)
