import os
import time
import subprocess
import argparse
import datetime
import sys
import json
import logging
import platform

# Constants
CONFIG_FILE = "config.json"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sync.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class GitSync:
    def __init__(self, repo_path, idle_threshold, remote_url=None):
        self.repo_path = repo_path
        self.idle_threshold = idle_threshold
        self.remote_url = remote_url
        self.interval = 5
        self.pending_changes_since = None

    def run_git(self, command, check=True):
        """Executes a git command in the repository path."""
        try:
            result = subprocess.run(
                ["git"] + command,
                cwd=self.repo_path,
                check=check,
                capture_output=True,
                text=True,
                shell=False
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if "up to date" not in e.stderr and "no changes" not in e.stderr:
                logger.error(f"Git error: {e.stderr.strip()}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def is_git_repo(self):
        return os.path.isdir(os.path.join(self.repo_path, ".git"))

    def initialize_repo(self):
        logger.info("Initializing new git repository...")
        self.run_git(["init"])
        if self.remote_url:
            self.run_git(["remote", "add", "origin", self.remote_url])
        self.run_git(["add", "."])
        self.run_git(["commit", "-m", "Initial commit from Obsidian Git Sync"])
        logger.info("Repository initialized.")

    def get_last_modified_time(self):
        """Recursively finds the most recent modification time in the directory."""
        last_mtime = 0
        for root, dirs, files in os.walk(self.repo_path):
            if '.git' in dirs:
                dirs.remove('.git')
            for f in files:
                full_path = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(full_path)
                    if mtime > last_mtime:
                        last_mtime = mtime
                except OSError:
                    continue
        return last_mtime

    def repair_connection(self):
        """Force refresh network cache and reset remote URL if needed."""
        logger.info("Starting connection repair...")
        
        # 1. Clear proxy settings (common cause for 500 errors)
        logger.info("Clearing Git proxy settings...")
        subprocess.run(["git", "config", "--global", "--unset", "http.proxy"], check=False)
        subprocess.run(["git", "config", "--global", "--unset", "https.proxy"], check=False)
        
        # 2. Reset Remote URL if origin exist
        if self.remote_url:
            logger.info(f"Resetting remote URL to: {self.remote_url}")
            self.run_git(["remote", "set-url", "origin", self.remote_url], check=False)
        
        # 3. Try to pull
        logger.info("Attempting to pull changes...")
        res = self.run_git(["pull"], check=False)
        if res is not None:
            logger.info("Repair completed successfully.")
        else:
            logger.warning("Repair finished, but pull still failing. Check your credentials or network.")

    def sync(self):
        try:
            process = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False
            )
            status_output = process.stdout.strip()
        except Exception as e:
            logger.error(f"Error checking status: {e}")
            return

        if status_output:
            last_mtime = self.get_last_modified_time()
            current_time = time.time()
            idle_time = current_time - last_mtime
            
            if idle_time >= self.idle_threshold:
                logger.info(f"Changes detected. Idle for {int(idle_time)}s. Syncing...")
                self.commit_and_push()
            elif self.pending_changes_since is None:
                self.pending_changes_since = current_time
                logger.info(f"Changes detected. Waiting for idle ({self.idle_threshold}s)...")
        else:
            self.pending_changes_since = None
            self.pull_changes()

    def commit_and_push(self):
        try:
            self.run_git(["add", "."])
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.run_git(["commit", "-m", f"Auto sync: {timestamp}"])
            
            self.pull_changes()
            
            logger.info("Pushing to remote...")
            if self.run_git(["push"]) is not None:
                logger.info("Push successful.")
            else:
                logger.error("Push failed. You may need to run with --repair.")
        except Exception as e:
            logger.error(f"Sync failed: {e}")

    def pull_changes(self):
        try:
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
    parser.add_argument("--repair", action="store_true", help="Repair Git connection (proxy & remote URL).")
    parser.add_argument("repo_path", nargs="?", help="Path to the Obsidian vault.")
    parser.add_argument("--idle_threshold", type=int, help="Seconds of inactivity before syncing.")
    
    args = parser.parse_args()
    config = load_config()

    repo_path = args.repo_path or config.get("repo_path")
    idle_threshold = args.idle_threshold or config.get("idle_threshold", 60)
    remote_url = config.get("remote_url")

    if not repo_path or args.setup:
        print("--- Obsidian Git Sync Setup ---")
        if not repo_path:
            while not repo_path:
                repo_path = input("Enter the absolute path to your Obsidian vault: ").strip()
        
        remote_url = input(f"Enter GitHub Remote URL [{remote_url or 'None'}]: ").strip() or remote_url
        
        config = {
            "repo_path": repo_path,
            "idle_threshold": idle_threshold,
            "remote_url": remote_url
        }
        save_config(config)

    syncer = GitSync(repo_path, idle_threshold, remote_url=remote_url)
    
    if args.repair:
        syncer.repair_connection()
        return

    if not syncer.is_git_repo():
        logger.warning(f"{repo_path} is not a git repository.")
        choice = input("Do you want to initialize it now? [y/N]: ").strip().lower()
        if choice == 'y':
            if not remote_url:
                 remote_url = input("Enter GitHub clone URL: ").strip()
                 syncer.remote_url = remote_url
            syncer.initialize_repo()
        else:
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
