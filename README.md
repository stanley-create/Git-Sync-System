# Obsidian Git Sync

A simple, cross-platform (Windows & macOS) Python script to automatically synchronize your Obsidian vault with a GitHub repository.

## Features
- **Auto-Sync**: Automatically pulls, adds, commits, and pushes changes.
- **Cross-Platform**: Works on Windows and macOS.
- **Conflict Avoidance**: Uses `git pull --rebase` to minimize merge commits.
- **Configurable**: Set custom sync intervals and repository paths.

## Prerequisites
- **Python 3.x** installed.
- **Git** installed and configured (user name, email).
- An existing **GitHub repository** initialized in your Obsidian vault.
- SSH keys or Credential Manager configured so `git push` / `git pull` does not ask for a password.

## Installation
1.  Clone this repository or download the script.
    ```bash
    git clone https://github.com/stanley-create/Git-Sync-System.git
    cd Git-Sync-System
    ```

## Usage (Easy Method)

### Windows
1.  Double-click **`start.bat`**.
2.  The first time you run it, it will ask for your **Obsidian Vault path** and settings.
3.  Future runs will use these saved settings automatically.

### macOS / Linux
1.  Open Terminal.
2.  Run the start script:
    ```bash
    ./start.sh
    ```
    *(You may need to run `chmod +x start.sh` once to make it executable)*.

## Usage (Manual / Command Line)
You can still run the script manually if you prefer:

```bash
python sync.py --setup
```
Or with arguments:
```bash
python sync.py [path_to_vault] --idle_threshold 60
```

### Configuration
Settings are saved to `config.json`. You can edit this file directly to change your preferences:
```json
{
    "repo_path": "C:\\Users\\User\\Documents\\ObsidianVault",
    "idle_threshold": 60,
    "interval": 10
}
```

## Running in Background
### Windows
You can use **Task Scheduler** to run the script at login.
1.  Open Task Scheduler.
2.  Create a Basic Task.
3.  Trigger: "When I log on".
4.  Action: "Start a program".
    - Program/script: `pythonw.exe` (Use `pythonw` to run without a window).
    - Add arguments: `C:\path\to\ObsidianGitSync\sync.py C:\path\to\your\vault --idle_threshold 60`
    - Start in: `C:\path\to\ObsidianGitSync\`

### macOS
You can use **cron** or **launchd**.
**Using Cron:**
1.  Open terminal and type `crontab -e`.
2.  Add the line:
    ```bash
    @reboot /usr/bin/python3 /path/to/ObsidianGitSync/sync.py /path/to/your/vault &
    ```

## Logic
The script runs in a loop (every 10 seconds by default):
1.  **Check Status**: Looks for local changes.
2.  **If Clean**:
    -   `git pull --rebase`: Updates local with remote changes.
3.  **If Dirty (Changes Detected)**:
    -   Checks the last modified time of all files.
    -   Calculates `idle_time`.
    -   **If idle_time > idle_threshold**:
        -   `git add .`
        -   `git commit -m "Auto sync: <timestamp>"`
        -   `git pull --rebase` (to handle remote changes safely)
        -   `git push`
    -   **Else**:
        -   Waits for user to stop editing (Resets timer if files change again).
