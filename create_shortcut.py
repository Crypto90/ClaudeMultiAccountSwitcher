"""Helper to generate Windows 11 desktop and start menu shortcuts."""

import os
import sys
import subprocess
from pathlib import Path
from core.config import config


def create_desktop_shortcut_for_account(account_id: str) -> str:
    """Create a Windows desktop shortcut that switches directly into the target account."""
    accounts = config.load_accounts()
    acc = accounts.get("accounts", {}).get(account_id)
    if not acc:
        raise ValueError(f"Account {account_id} not found")

    account_name = acc.get("name", "Claude")
    safe_name = "".join(c for c in account_name if c.isalnum() or c in (" ", "-", "_")).strip()
    desktop_dir = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    shortcut_path = desktop_dir / f"Claude - {safe_name}.lnk"

    python_exe = sys.executable
    script_path = Path(__file__).parent / "main.py"
    icon_path = r"C:\Program Files\WindowsApps\Claude_2.110.1.0_x64__pzs8sxrjxfjjc\app\Claude.exe"

    # Use PowerShell WScript.Shell to create shortcut cleanly
    ps_cmd = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{str(shortcut_path)}')
    $Shortcut.TargetPath = '{python_exe}'
    $Shortcut.Arguments = '"{str(script_path)}" --switch "{account_id}"'
    $Shortcut.WorkingDirectory = '{str(Path(__file__).parent)}'
    if (Test-Path '{icon_path}') {{
        $Shortcut.IconLocation = '{icon_path},0'
    }}
    $Shortcut.Save()
    """

    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    return str(shortcut_path)


def create_app_shortcut() -> str:
    """Create a main desktop shortcut for Claude Multi-Account Switcher."""
    desktop_dir = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    shortcut_path = desktop_dir / "Claude Switcher.lnk"

    python_exe = sys.executable
    script_path = Path(__file__).parent / "main.py"
    icon_path = r"C:\Program Files\WindowsApps\Claude_2.110.1.0_x64__pzs8sxrjxfjjc\app\Claude.exe"

    ps_cmd = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{str(shortcut_path)}')
    $Shortcut.TargetPath = '{python_exe}'
    $Shortcut.Arguments = '"{str(script_path)}"'
    $Shortcut.WorkingDirectory = '{str(Path(__file__).parent)}'
    if (Test-Path '{icon_path}') {{
        $Shortcut.IconLocation = '{icon_path},0'
    }}
    $Shortcut.Save()
    """

    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    return str(shortcut_path)


if __name__ == "__main__":
    path = create_app_shortcut()
    print(f"Created application shortcut: {path}")
