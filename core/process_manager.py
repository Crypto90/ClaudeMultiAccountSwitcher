"""Process lifecycle management for Claude Desktop on Windows 11."""

import os
import time
import ctypes
import logging
import subprocess
import psutil
from pathlib import Path
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

    @classmethod
    def _get_claude_processes(cls) -> List[psutil.Process]:
        """Discover all active Claude processes safely."""
        procs = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info["name"] or "").lower()
                if name in ("claude.exe", "claude"):
                    try:
                        exe = (proc.exe() or "").lower()
                        if "claude-code" in exe:
                            continue
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                    procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs

    @classmethod
    def close_claude(cls, timeout_sec: float = 6.0) -> bool:
        """
        Gracefully close all Claude Desktop processes.
        Sends WM_CLOSE first to allow Electron to flush SQLite and LevelDB caches,
        falling back to taskkill process tree termination if timeout expires.
        """
        claude_procs = cls._get_claude_processes()
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

        # Step 2: Wait for processes to exit gracefully (up to 2.5s)
        grace_start = time.time()
        while time.time() - grace_start < min(timeout_sec, 2.5):
            if not cls._get_claude_processes():
                break
            time.sleep(0.2)

        # Step 3: Force kill any remaining processes using taskkill and proc.kill()
        remaining = cls._get_claude_processes()
        if remaining:
            logger.info(f"Terminating {len(remaining)} lingering Claude processes via taskkill...")
            try:
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(
                    ["taskkill", "/F", "/IM", "claude.exe", "/T"],
                    capture_output=True,
                    timeout=3.0,
                    creationflags=creation_flags
                )
            except Exception as e:
                logger.warning(f"taskkill failed: {e}")

            for proc in remaining:
                try:
                    if proc.is_running():
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        # Step 4: Ensure file locks are released
        lock_wait_start = time.time()
        while time.time() - lock_wait_start < 4.0:
            if not detector.is_claude_running() and not detector.is_cookies_locked():
                return True
            time.sleep(0.2)

        return not detector.is_claude_running()

    @classmethod
    def _find_direct_executable(cls) -> Optional[str]:
        """Dynamically locate installed Claude executable on Windows."""
        # 1. Check WindowsApps installed package
        base_apps = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "WindowsApps"
        if base_apps.exists():
            try:
                matches = list(base_apps.glob("Claude_*_x64__pzs8sxrjxfjjc/app/claude.exe"))
                if matches:
                    # Return latest modified version
                    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    return str(matches[0])
            except Exception:
                pass

        # 2. Check LocalAppData Programs path
        local_app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Claude" / "Claude.exe"
        if local_app.exists():
            return str(local_app)

        return None

    @classmethod
    def launch_claude(cls, timeout_sec: float = 4.0) -> bool:
        """
        Launch Claude Desktop using native Windows ShellExecute (os.startfile).
        Falls back to explorer.exe shell URI or dynamic direct executable, and verifies
        that Claude processes are actively running before returning.
        """
        app_uri = "shell:AppsFolder\\Claude_pzs8sxrjxfjjc!Claude"
        direct_exe = cls._find_direct_executable()

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
        if not launched and direct_exe and os.path.exists(direct_exe):
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
        if not detector.is_claude_running() and direct_exe and os.path.exists(direct_exe):
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
