# Obsidian Git Sync (Enhanced)

A robust, cross-platform (Windows & macOS) Python script to automatically synchronize your Obsidian vault with a GitHub repository.

## New Features
- **Smart Idle Detection**: Only checks modified files, significantly improving performance for large vaults.
- **Robust Logging**: actions are logged to `sync.log`.
- **Auto-Initialization**: Detects if your vault is not a git repo and helps you set it up.
- **Background Sync**: Can register itself on Windows Startup.

## Prerequisites
- **Python 3.x** installed.
- **Git** installed and configured.
- (Optional) A GitHub repository URL if you want to upload to the cloud.

## Installation
To use this system, you first need to download the code:
```bash
git clone https://github.com/stanley-create/Git-Sync-System
```

## Quick Start

1.  **Double-click `start.bat`**.
2.  The first time you run it, it will **ask for your GitHub Email and Username**.
    - This is required so Git knows who is making the backups.
3.  Then, it will **ask you to enter the path** to your Obsidian Vault.
    - Example: `C:\Users\Name\Documents\MyVault`
4.  It will also ask for your GitHub repository URL (optional but recommended).
5.  The script will save your settings and start monitoring.

## Run at Startup (Windows)
To have this run automatically when you log in:
1.  Open a terminal in this folder.
2.  Run: `python sync.py --install-startup`

# Setting up Obsidian Auto-Sync via Shell Commands

Follow these steps to ensure your `start.bat` script runs automatically every time you open Obsidian.

### Step 1: Install Shell Commands Plugin

1. Open **Obsidian Settings**.
2. Navigate to **Community plugins** and click **Browse**.
3. Search for **"Shell Commands"** and click **Install**.
4. After installation, click **Enable**.

### Step 2: Create the Sync Command

1. Go to the **Shell Commands** settings page.
2. Click the **"Create new command"** button.
3. In the **Command** field, enter the absolute path to your batch file:
```text
"C:\Users\cg102\Git-Sync-System\start.bat"
```
*(Note: Keep the double quotes if your path contains spaces.)*
4. Give it an **Alias** like: `Obsidian Git Auto Sync`.

### Step 3: Configure Execution Events (Triggers)

To make the script run on startup:

1. Click the **Events** icon (lightning bolt symbol) next to your new command.
2. Click **Add new event**.
3. Select **"Obsidian starts"** from the list.
4. This ensures the Python monitoring script starts as soon as you open your vault.

![Shell Event Settings](assets/shell_event_settings.png)

### Step 4: Enable Background Execution (Silent Mode)

To prevent a black CMD window from popping up and interrupting your work:

1. In the command settings, look for **Output handling**.
2. Set **Output channel** for stdout/stderr to **"Ignore"**.
3. Set **Output handling mode** to **"Realtime"** to ensure long-running processes are handled correctly.

![Shell Output Settings](assets/shell_output_settings.png)

### Step 5: Verify the Automation

1. Restart your Obsidian.
2. Check your **Windows Task Manager** (Ctrl + Shift + Esc).
3. You should see a `python.exe` process running in the background.
4. Try editing a note, wait for 20-60 seconds, and check your GitHub repository to see if the changes were pushed automatically.

---

### Troubleshooting Tip

If the script doesn't seem to trigger, you can manually run the command once using the **Command Palette** (Ctrl + P) and searching for: `Shell Commands: Execute: Obsidian Git Auto Sync`.

## Configuration
Settings are saved to `config.json`.
```json
{
    "repo_path": "C:\\Users\\2026\\Documents\\Obsidian Vault",
    "idle_threshold": 60,
    "remote_url": "https://github.com/your/repo.git"
}
```

## Troubleshooting & Repair

If you encounter **500 errors**, **403 forbidden**, or **failed to push** errors, we have a built-in repair tool.

### 2. Manual Git Identity Setup
If the script doesn't prompt you or you prefer to set it up manually, run these commands in CMD:
```dos
git config --global user.email "your-email@example.com"
git config --global user.name "Your Name"
```

### 3. Manual Repair
Open a terminal in the folder and run:
```bash
python sync.py --repair
```
**This will automatically:**
- Clear stuck proxy settings.
- Reset the remote connection to GitHub.
- Link your local branch to the cloud.
- Automatically resolve "failed to push" conflicts by rebasing.

### 2. Identity Issues
If your commits don't show your name, or Git complains about "Author identity unknown", run:
```bash
python sync.py --setup
```
This will allow you to re-enter your GitHub Email and Username.

## How it Works
- **Identity Check**: Always ensures Git knows who you are before syncing.
- **Checks changes**: Every 20 seconds.
- **Syncs**: If changes are detected and you stop typing for 60 seconds (idle), it commits and pushes.
- **Conflicts**: Automatically tries `git pull --rebase` to avoid merge conflicts.
- **Upstream Setup**: Automatically handles the first push to a new repository.
