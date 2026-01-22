import os
import time
import subprocess
import argparse
import datetime
import sys
import json
import logging
import platform
import shutil

# Constants
CONFIG_FILE = "config.json"

def run_git_command(command, repo_path):
    """Executes a git command in the specified repository path."""
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
            shell=False
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if "up to date" not in e.stderr and "no changes" not in e.stderr:
             pass
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def get_last_modified_time(repo_path):
    """Recursively finds the most recent modification time in the directory."""
    last_mtime = 0
    for root, dirs, files in os.walk(repo_path):
        if '.git' in dirs:
            dirs.remove('.git') # Ignore .git directory
        for f in files:
            full_path = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(full_path)
                if mtime > last_mtime:
                    last_mtime = mtime
            except OSError:
                continue
    return last_mtime

def sync_repo(repo_path, idle_threshold):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    # 1. Check status
    try:
        process = subprocess.run(
            ["git", "status", "--porcelain"], 
            cwd=repo_path, 
            capture_output=True, 
            text=True, 
            check=False
        )
        status_output = process.stdout.strip()
    except Exception as e:
        print(f"[{timestamp}] Error checking status: {e}")
        return

    if status_output:
        last_mtime = get_last_modified_time(repo_path)
        current_time = time.time()
        idle_time = current_time - last_mtime
        
        if idle_time >= idle_threshold:
            print(f"[{timestamp}] Changes detected. Idle for {int(idle_time)}s. Syncing...")
            run_git_command(["git", "add", "."], repo_path)
            commit_msg = f"Auto sync: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            run_git_command(["git", "commit", "-m", commit_msg], repo_path)
            print(f"[{timestamp}] Committed changes.")
            print(f"[{timestamp}] Pulling remote changes...")
            pull_res = run_git_command(["git", "pull", "--rebase"], repo_path)
            if pull_res is None:
                print(f"[{timestamp}] Pull failed (conflict?). Please resolve manually.")
                return 
            print(f"[{timestamp}] Pushing to remote...")
            if run_git_command(["git", "push"], repo_path):
                print(f"[{timestamp}] Push successful.")
            else:
                if self.pending_changes_since is None:
                    self.pending_changes_since = current_time
                    logger.info(f"Changes detected. Waiting for idle ({self.idle_threshold}s)...")
        else:
            self.pending_changes_since = None
            # Only pull if we are clean
            # To avoid spamming log, we could simple do it quietly
            self.pull_changes()

    def commit_and_push(self):
        try:
            self.run_git(["add", "."])
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.run_git(["commit", "-m", f"Auto sync: {timestamp}"])
            
            self.pull_changes() # Pull before push to resolve simple conflicts
            
            logger.info("Pushing to remote...")
            self.run_git(["push"])
            logger.info("Push successful.")
        except Exception as e:
            logger.error(f"Sync failed: {e}")

    def pull_changes(self):
        try:
            # quietly try to pull
            self.run_git(["pull", "--rebase"], check=False)
        except Exception:
            pass

    def add_to_startup(self):
        """Adds the script to Windows startup."""
        if platform.system() != "Windows":
            logger.warning("Startup registration is only supported on Windows.")
            return

        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            
            # Use pythonw.exe to run without window
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            script_path = os.path.abspath(__file__)
            cmd = f'"{python_exe}" "{script_path}" "{self.repo_path}" --idle_threshold {self.idle_threshold}'
            
            winreg.SetValueEx(key, "ObsidianGitSync", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            logger.info("Successfully added to Windows Startup.")
        except Exception as e:
            logger.error(f"Failed to add to startup: {e}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        logger.info(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def main():
    parser = argparse.ArgumentParser(description="Auto-sync Obsidian vault with GitHub.")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup wizard.")
    parser.add_argument("--install-startup", action="store_true", help="Add to Windows startup.")
    parser.add_argument("repo_path", nargs="?", help="Path to the Obsidian vault.")
    parser.add_argument("--idle_threshold", type=int, help="Seconds of inactivity before syncing.")
    
    args = parser.parse_args()
    config = load_config()

    # Resolve Configuration
    repo_path = args.repo_path or config.get("repo_path")
    idle_threshold = args.idle_threshold or config.get("idle_threshold", 60)
    remote_url = config.get("remote_url")

    # If no path configured, strictly prompt the user
    if not repo_path:
        print("--- Obsidian Git Sync Setup ---")
        while not repo_path:
            repo_path = input("Enter the absolute path to your Obsidian vault: ").strip()
            if not repo_path:
                print("Path cannot be empty.")
        
        # Ask for remote URL optional
        if not remote_url:
            remote_url = input("Enter GitHub Remote URL (leave empty if already set): ").strip()
        
        # Save this new config
        config = {
            "repo_path": repo_path,
            "idle_threshold": idle_threshold,
            "remote_url": remote_url
        }
        save_config(config)

    # Initialize System
    syncer = GitSync(repo_path, idle_threshold, remote_url=remote_url)
    
    if not syncer.is_git_repo():
        logger.warning(f"{repo_path} is not a git repository.")
        choice = input("Do you want to initialize it now? [y/N]: ").strip().lower()
        if choice == 'y':
            if not remote_url:
                 remote_url = input("Enter GitHub clone URL to link to (or enter to skip): ").strip()
                 syncer.remote_url = remote_url
            syncer.initialize_repo()
        else:
            logger.error("Cannot sync a non-git repository.")
            return

    if args.install_startup:
        syncer.add_to_startup()

    logger.info(f"Monitoring: {repo_path}")
    logger.info(f"Idle Threshold: {idle_threshold}s")
    logger.info("Press Ctrl+C to stop.")

    try:
        while True:
            syncer.sync()
            time.sleep(syncer.interval)
    except KeyboardInterrupt:
        logger.info("Stopping auto-sync.")

if __name__ == "__main__":
    main()
