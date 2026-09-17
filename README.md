# Claude Multi-Account Switcher for Windows 11 ✦

A fast, lightweight, and native Windows 11 tool to switch between different Claude Desktop accounts seamlessly without losing sign-ins or re-entering credentials.

Includes **Rate Limit Continuity (Selective Session Transfer)**: Pick in-progress or rate-limited sessions and move them between accounts with one click to keep working without interruption.

---

## Key Features

- 🛡️ **Zero Login Loss Guarantee**: Automatically creates an immutable snapshot of your active account upon first run so your original login can never be lost.
- ⚡ **Instant 1-Click Swapping**: Switches accounts in under 1 second.
- 💾 **Zero Disk Bloat**: Leaves the 12 GB Coworker VM (`vm_bundles`) and binaries shared in place, copying only the ~10–15 MB session payload per account.
- 🔀 **Selective Session Transfer (Rate Limit Continuity)**:
  - Browse all Claude Cowork / Agent Mode / Code sessions in the **Session Hub**.
  - Select specific sessions via checkboxes.
  - Transfer or carry over sessions to another account when one account hits rate limits.
- 🖥️ **Windows 11 Fluent Dark UI**: Built with PyQt6, featuring Segoe UI Variable fonts, acrylic/mica styling, live Claude process status, and responsive cards.
- 📌 **System Tray Integration**: Sits in the Windows taskbar tray for instant account switching without opening the main window.
- 🔗 **Desktop Shortcuts**: Generate 1-click desktop shortcuts for specific accounts (e.g. `Claude - Work.lnk`).
- 🧩 **Shared MCP Server Configurations**: Custom MCP servers and tools can be automatically shared across all accounts.

---

## Quick Start

### 1. Launch the Application
Simply double-click `run.bat` or run:
```bash
python main.py
```

### 2. First Run (Automatic Safe Backup)
On first launch, the tool detects your active Claude Desktop login (Account UUID) and creates an immutable baseline backup in:
```
%APPDATA%\ClaudeSwitcher\backups\initial_session\
```
Your current account is registered as **Main Account**.

### 3. Adding More Accounts
1. Click **+ Add Account**.
2. Enter a friendly name (e.g., "Work Account", "Testing Org") and choose an avatar color.
3. Click **Start Setup & Open Claude**.
4. Claude Desktop opens to the sign-in screen.
5. Log in with your second account.
6. The switcher automatically detects the new login, saves the profile, and adds it to your dashboard!

### 4. Switching Accounts
- From the Dashboard: Click **Switch To This Account**.
- From the Windows System Tray: Right-click the tray icon and pick the account.
- If prompted, you can choose to carry over your current in-progress session to the target account!

### 5. Transferring Sessions (Rate-Limit Recovery)
1. Open the **Session Hub** tab.
2. Select 1 or more specific sessions you want to transfer.
3. Click **Transfer Selected**.
4. Choose the destination account and confirm.
5. Switch to that account in Claude Desktop — your session and progress are right there!

---

## CLI Usage

```bash
# List all registered accounts
python main.py --list

# Switch directly to an account
python main.py --switch account_primary

# Start minimized to system tray
python main.py --tray
```

---

## Architecture & Storage

- Application Data: `%APPDATA%\ClaudeSwitcher\`
- Account Profiles: `%APPDATA%\ClaudeSwitcher\profiles\`
- Immutable Baseline Backup: `%APPDATA%\ClaudeSwitcher\backups\initial_session\`
- Excluded from duplication: `vm_bundles` (12 GB), `claude-code` (450 MB), `Cache` (Chromium cache).
