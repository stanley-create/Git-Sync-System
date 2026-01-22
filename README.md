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

## Quick Start

1.  **Double-click `start.bat`**.
2.  The first time you run it, it will **ask you to enter the path** to your Obsidian Vault.
    - Example: `C:\Users\Name\Documents\MyVault`
3.  It will also ask for your GitHub repository URL (optional if you haven't linked it yet).
4.  The script will save your settings and start monitoring.

## Run at Startup (Windows)
To have this run automatically when you log in:
1.  Open a terminal in this folder.
2.  Run: `python sync.py --install-startup`

## Configuration
Settings are saved to `config.json`.
```json
{
    "repo_path": "C:\\Users\\cg102\\Documents\\Obsidian Vault",
    "idle_threshold": 60,
    "remote_url": "https://github.com/your/repo.git"
}
```

## How it Works
- **Checks changes**: Every 10 seconds.
- **Syncs**: If changes are detected and you stop typing for 60 seconds (idle), it commits and pushes.
- **Conflicts**: Automatically tries `git pull --rebase` to avoid merge conflicts.
