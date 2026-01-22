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

    def check_identity(self):
        """Checks if Git user.email and user.name are configured."""
        email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout.strip()
        name = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
        
        if not email or not name:
            logger.warning("Git identity not configured.")
            if not email:
                email = input("Enter your GitHub Email: ").strip()
                subprocess.run(["git", "config", "--global", "user.email", email], check=True)
            if not name:
                name = input("Enter your GitHub Username: ").strip()
                subprocess.run(["git", "config", "--global", "user.name", name], check=True)
            logger.info("Git identity configured successfully.")

    def repair_connection(self):
        """Force refresh network cache and reset remote URL if needed."""
        logger.info("Starting connection repair...")
        
        # 1. Clear proxy settings (common cause for 500 errors)
        logger.info("1. Clearing Git proxy settings...")
        subprocess.run(["git", "config", "--global", "--unset", "http.proxy"], check=False)
        subprocess.run(["git", "config", "--global", "--unset", "https.proxy"], check=False)
        
        # 2. Set autoSetupRemote (prevents "no upstream" errors)
        logger.info("2. Setting push.autoSetupRemote to true...")
        subprocess.run(["git", "config", "--global", "push.autoSetupRemote", "true"], check=False)
        
        # 3. Reset Remote URL if origin exist
        if self.remote_url:
            logger.info(f"3. Resetting remote URL to: {self.remote_url}")
            self.run_git(["remote", "set-url", "origin", self.remote_url], check=False)
        
        # 4. Try to push with upstream tracking
        logger.info("4. Attempting to push with upstream tracking...")
        push_res = subprocess.run(["git", "push", "--set-upstream", "origin", "main"], cwd=self.repo_path, capture_output=True, text=True)
        
        if push_res.returncode == 0:
            logger.info("Repair completed successfully. Branch is linked and pushed.")
        else:
            if "failed to push some refs" in push_res.stderr:
                logger.info("Conflict detected (remote has changes). Running rebase...")
                self.run_git(["pull", "origin", "main", "--rebase"], check=False)
                logger.info("Retrying push...")
                if self.run_git(["push"]) is not None:
                    logger.info("Repair completed successfully after rebase.")
                else:
                    logger.warning("Push still failing after rebase. Please check manually.")
            else:
                logger.warning(f"Repair finished, but push failed: {push_res.stderr.strip()}")

    def sync(self):
        # Ensure identity is set before syncing
        self.check_identity()
        
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
            # Check if remote exists before pulling
            res = self.run_git(["pull", "--rebase"], check=False)
            if res is None:
                # Silently fail pull if no remote or other issues, 
                # but log it if it's a real error (not "no remote" type things)
                pass
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

    # Resolve interactive setup
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
    
    if args.repair or args.setup:
        syncer.check_identity()
        if args.repair:
            syncer.repair_connection()
            return

    if not syncer.is_git_repo():
        logger.warning(f"{repo_path} is not a git repository.")
        choice = input("Do you want to initialize it now? [y/N]: ").strip().lower()
        if choice == 'y':
            syncer.check_identity()
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
