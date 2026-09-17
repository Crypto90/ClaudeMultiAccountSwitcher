"""Entry point for Claude Multi-Account Switcher on Windows 11."""

import sys
import argparse
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from core.config import config
from core.profile_manager import profile_manager
from ui.styles import FLUENT_DARK_QSS

from PyQt6.QtGui import QFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ClaudeSwitcher")


def run_cli_switch(account_id: str):
    """Switch account via CLI argument without full GUI."""
    accounts = config.load_accounts()
    acc = accounts.get("accounts", {}).get(account_id)
    if not acc:
        print(f"Error: Account '{account_id}' not found.")
        sys.exit(1)

    print(f"Switching to '{acc.get('name')}'...")
    try:
        profile_manager.switch_account(account_id)
        print("Switch complete! Claude Desktop launched.")
    except Exception as e:
        print(f"Failed to switch: {e}")
        sys.exit(1)


def run_cli_list():
    """Print registered accounts to terminal."""
    accounts = config.load_accounts()
    active_id = accounts.get("active_account_id")
    print("\nRegistered Claude Accounts:")
    print("-" * 50)
    for acc_id, acc in accounts.get("accounts", {}).items():
        prefix = "[ACTIVE] " if acc_id == active_id else "         "
        print(f"{prefix}{acc.get('name'):20} | ID: {acc_id:15} | UUID: {acc.get('account_uuid')}")
    print("-" * 50)


def main():
    parser = argparse.ArgumentParser(description="Claude Multi-Account Switcher for Windows 11")
    parser.add_argument("--switch", help="Directly switch to account ID without opening GUI")
    parser.add_argument("--list", action="store_true", help="List registered accounts")
    parser.add_argument("--tray", action="store_true", help="Start directly minimized to system tray")
    args = parser.parse_args()

    if args.list:
        run_cli_list()
        return

    if args.switch:
        run_cli_switch(args.switch)
        return

    # Start GUI application
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Claude Multi-Account Switcher")

    app_font = QFont("Segoe UI Variable Text", 10)
    app_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(app_font)

    app.setStyleSheet(FLUENT_DARK_QSS)

    from ui.main_window import MainWindow
    window = MainWindow()

    if not args.tray:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
