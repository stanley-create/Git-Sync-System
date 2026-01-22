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
LOG_FILE = "sync.log"
DEFAULT_INTERVAL = 10
DEFAULT_IDLE_THRESHOLD = 60

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GitSync")

class GitSync:
    def __init__(self, repo_path, idle_threshold=DEFAULT_IDLE_THRESHOLD, interval=DEFAULT_INTERVAL, remote_url=None):
        self.repo_path = os.path.abspath(repo_path)
        self.idle_threshold = idle_threshold
        self.interval = interval
        self.remote_url = remote_url
        self.pending_changes_since = None

    def run_git(self, args, check=True):
        """Executes a git command in the repository."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                check=check,
                capture_output=True,
                text=True,
                encoding='utf-8' # Ensure UTF-8 for non-English filenames
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if "up to date" not in e.stderr and "no changes" not in e.stderr:
                logger.debug(f"Git command failed: {' '.join(args)} | Error: {e.stderr.strip()}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error running git: {e}")
            raise

    def is_git_repo(self):
        return os.path.isdir(os.path.join(self.repo_path, ".git"))

    def initialize_repo(self):
        """Initializes git repo and sets remote if provided."""
        logger.info(f"Initializing git repository in {self.repo_path}...")
        try:
            self.run_git(["init"])
            self.run_git(["branch", "-M", "main"], check=False) # standard main branch
            
            # Create .gitignore if not exists
            gitignore_path = os.path.join(self.repo_path, ".gitignore")
            if not os.path.exists(gitignore_path):
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(".obsidian/workspace\n.obsidian/workspace-mobile\n.DS_Store\n")
                logger.info("Created default .gitignore")

            if self.remote_url:
                self.run_git(["remote", "add", "origin", self.remote_url], check=False)
                logger.info(f"Added remote origin: {self.remote_url}")
            
            # Initial commit
            self.run_git(["add", "."])
            self.run_git(["commit", "-m", "Initial commit by Git-Sync-System"], check=False)
            logger.info("Performed initial commit.")

        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")

    def get_modified_files(self):
        """Returns a list of modified files using git status."""
        try:
            status = self.run_git(["status", "--porcelain"])
            if not status:
                return []
            
            files = []
            for line in status.splitlines():
                # Format: XY PATH
                # XY are status codes (e.g., M , ??, A )
                if len(line) > 3:
                    file_path = line[3:].strip()
                    # Handle quoted paths (git sometimes quotes paths with spaces/non-ascii)
                    if file_path.startswith('"') and file_path.endswith('"'):
                        file_path = file_path[1:-1]
                    files.append(file_path)
            return files
        except Exception:
            return []

    def get_latest_mtime(self, files):
        """Gets the most recent modification time among the specified files."""
        max_mtime = 0
        for rel_path in files:
            full_path = os.path.join(self.repo_path, rel_path)
            if os.path.exists(full_path):
                try:
                    mtime = os.path.getmtime(full_path)
                    if mtime > max_mtime:
                        max_mtime = mtime
                except OSError:
                    pass
        return max_mtime

    def sync(self):
        """Main check and sync logic."""
        # 1. Check for local modifications
        modified_files = self.get_modified_files()

        if modified_files:
            current_time = time.time()
            last_mtime = self.get_latest_mtime(modified_files)
            
            # If we simply can't find an mtime (e.g. deleted files), assume 'now'
            if last_mtime == 0:
                last_mtime = current_time

            idle_time = current_time - last_mtime

            if idle_time >= self.idle_threshold:
                logger.info(f"Idle for {int(idle_time)}s. Syncing changes...")
                self.commit_and_push()
                self.pending_changes_since = None
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
