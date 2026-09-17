"""Process lifecycle management for Claude Desktop on Windows 11."""

import os
import time
import ctypes
import logging
import subprocess
import psutil
from typing import Optional, List
from core.config import config
from core.detector import detector

logger = logging.getLogger("ClaudeSwitcher.ProcessManager")

# Windows API constants
WM_CLOSE = 0x0010


def _find_window_handles_for_pid(pid: int) -> List[int]:
    """Find all top-level window handles owned by a process ID."""
    hwnds = []

    def enum_windows_proc(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            window_pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if window_pid.value == pid:
                hwnds.append(hwnd)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
    return hwnds


class ProcessManager:
    """Handles graceful termination, verification, and launch of Claude Desktop."""

    @staticmethod
    def close_claude(timeout_sec: float = 6.0) -> bool:
        """
        Gracefully close all Claude Desktop processes.
        Sends WM_CLOSE first to allow Electron to flush SQLite and LevelDB caches,
        falling back to process termination if timeout expires.
        """
        claude_procs = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = (proc.info["name"] or "").lower()
                exe = (proc.info["exe"] or "").lower()
                if "claude.exe" in name and "claude-code" not in exe:
                    claude_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not claude_procs:
            return True

        logger.info(f"Attempting graceful close of {len(claude_procs)} Claude processes...")

        # Step 1: Send WM_CLOSE to all top-level windows
        for proc in claude_procs:
            try:
                hwnds = _find_window_handles_for_pid(proc.pid)
                for hwnd in hwnds:
                    ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            except Exception as e:
                logger.debug(f"Could not post WM_CLOSE to PID {proc.pid}: {e}")

        # Step 2: Wait for processes to exit
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            alive_procs = [p for p in claude_procs if p.is_running()]
            if not alive_procs:
                break
            time.sleep(0.3)

        # Step 3: Force kill any remaining processes if still alive
        for proc in claude_procs:
            try:
                if proc.is_running():
                    logger.warning(f"Force terminating lingering Claude PID {proc.pid}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Step 4: Ensure file locks are released
        lock_wait_start = time.time()
        while time.time() - lock_wait_start < 4.0:
            if not detector.is_cookies_locked():
                return True
            time.sleep(0.2)

        return not detector.is_claude_running()

    @classmethod
    def launch_claude(cls, timeout_sec: float = 4.0) -> bool:
        """
        Launch Claude Desktop using native Windows ShellExecute (os.startfile).
        Falls back to explorer.exe shell URI or direct executable, and verifies
        that Claude processes are actively running before returning.
        """
        app_uri = "shell:AppsFolder\\Claude_pzs8sxrjxfjjc!Claude"
        direct_exe = r"C:\Program Files\WindowsApps\Claude_2.110.1.0_x64__pzs8sxrjxfjjc\app\claude.exe"

        # Step 1: Native Windows ShellExecute via os.startfile (fastest and most reliable on Windows 11)
        launched = False
        try:
            logger.info(f"Launching Claude Desktop via os.startfile('{app_uri}')")
            os.startfile(app_uri)
            launched = True
        except Exception as e:
            logger.warning(f"os.startfile failed: {e}. Attempting explorer.exe fallback...")

        # Step 2: Fallback via explorer.exe shell invocation
        if not launched:
            try:
                subprocess.Popen(["explorer.exe", app_uri])
                launched = True
            except Exception as e:
                logger.warning(f"explorer.exe launch failed: {e}. Attempting direct executable...")

        # Step 3: Direct executable fallback if needed
        if not launched and os.path.exists(direct_exe):
            try:
                subprocess.Popen([direct_exe])
                launched = True
            except Exception as e:
                logger.error(f"Direct executable launch failed: {e}")

        # Step 4: Verification loop — confirm Claude Desktop has started
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            if detector.is_claude_running():
                proc_count = detector.get_claude_process_count()
                logger.info(f"Claude Desktop successfully started and running ({proc_count} processes).")
                return True
            time.sleep(0.25)

        # Final check & direct executable rescue if shell launch was delayed
        if not detector.is_claude_running() and os.path.exists(direct_exe):
            try:
                logger.info("Claude not detected within timeout, launching direct executable fallback...")
                subprocess.Popen([direct_exe])
                time.sleep(1.0)
            except Exception as ex:
                logger.error(f"Rescue launch failed: {ex}")

        is_running = detector.is_claude_running()
        if is_running:
            logger.info("Claude Desktop confirmed running.")
        else:
            logger.error("Claude Desktop launch failed to produce active processes.")
        return is_running

    @classmethod
    def restart_claude(cls) -> bool:
        """Restart Claude Desktop gracefully."""
        cls.close_claude()
        time.sleep(0.5)
        return cls.launch_claude()


process_manager = ProcessManager()
