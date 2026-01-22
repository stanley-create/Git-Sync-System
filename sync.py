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
LOG_FILE = "sync.log"
DEFAULT_INTERVAL = 20
DEFAULT_IDLE_THRESHOLD = 60

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GitSync")

class GitSync:
    def __init__(self, repo_path, idle_threshold=DEFAULT_IDLE_THRESHOLD, remote_url=None):
        self.repo_path = os.path.abspath(repo_path)
        self.idle_threshold = idle_threshold
        self.remote_url = remote_url
        self.interval = DEFAULT_INTERVAL
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
                errors='replace' # Handle non-utf-8 output
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip()
            if "up to date" not in error_msg and "no changes" not in error_msg:
                logger.debug(f"Git command failed: {' '.join(args)} | Error: {error_msg}")
            # Attach stderr to the exception so callers can see it
            e.args = (e.args[0], f"Error: {error_msg}")
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
            self.run_git(["branch", "-M", "main"], check=False)
            
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
            self.run_git(["commit", "-m", "Initial commit from Obsidian Git Sync"], check=False)
            logger.info("Performed initial commit. Pushing to remote...")
            try:
                self.run_git(["push", "-u", "origin", "main"], check=True)
                logger.info("Initial push successful.")
            except Exception as e:
                logger.warning(f"Initial push failed: {e}. It will retry during normal sync.")
            
            logger.info("Initialization complete.")

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
                if len(line) > 3:
                    file_path = line[3:].strip()
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

    def check_identity(self):
        """Checks if Git user.email and user.name are configured."""
        try:
            email = self.run_git(["config", "user.email"], check=False)
            name = self.run_git(["config", "user.name"], check=False)
            
            if not email or not name:
                logger.warning("Git identity not configured.")
                if not email:
                    email = input("Enter your GitHub Email: ").strip()
                    subprocess.run(["git", "config", "--global", "user.email", email], check=True)
                if not name:
                    name = input("Enter your GitHub Username: ").strip()
                    subprocess.run(["git", "config", "--global", "user.name", name], check=True)
                logger.info("Git identity configured successfully.")
        except Exception as e:
            logger.error(f"Error checking identity: {e}")

    def repair_connection(self):
        """Force refresh network cache and reset remote URL if needed."""
        logger.info("Starting connection repair...")
        
        # 1. Clear proxy settings (common cause for 500 errors)
        logger.info("1. Clearing Git proxy settings...")
        subprocess.run(["git", "config", "--global", "--unset", "http.proxy"], check=False)
        subprocess.run(["git", "config", "--global", "--unset", "https.proxy"], check=False)
        
        # 1b. Increase postBuffer for large pushes (helps with connection resets)
        logger.info("1b. Increasing Git postBuffer to 500MB...")
        subprocess.run(["git", "config", "--global", "http.postBuffer", "524288000"], check=False)
        
        # 2. Set autoSetupRemote
        logger.info("2. Setting push.autoSetupRemote to true...")
        subprocess.run(["git", "config", "--global", "push.autoSetupRemote", "true"], check=False)
        
        if self.remote_url:
            logger.info(f"3. Resetting remote URL to: {self.remote_url}")
            self.run_git(["remote", "set-url", "origin", self.remote_url], check=False)
        
        logger.info("4. Attempting to push with upstream tracking...")
        try:
            # First try a normal push
            self.run_git(["push", "--set-upstream", "origin", "main"], check=True)
            logger.info("Repair completed successfully!")
        except Exception as e:
            logger.info(f"Standard push failed ({e}). Attempting to sync with remote history...")
            try:
                # Common issue: unrelated histories or remote has a README. Try pulling first.
                logger.info("Pulling remote changes (allowing unrelated histories)...")
                self.run_git(["pull", "origin", "main", "--rebase", "--allow-unrelated-histories"], check=False)
                
                logger.info("Retrying push...")
                self.run_git(["push", "-u", "origin", "main"], check=True)
                logger.info("Repair completed successfully after synchronization!")
            except Exception as final_e:
                logger.error(f"Repair failed: {final_e}")
                logger.warning("TIP: Check if your GitHub repository is initialized and your internet connection is stable.")

    def is_ahead(self):
        """Checks if there are local commits not yet pushed to remote."""
        try:
            ahead = self.run_git(["rev-list", "--count", "origin/main..main"], check=False)
            if ahead and ahead.isdigit() and int(ahead) > 0:
                return True
        except Exception:
            pass
        return False

    def sync(self):
        """Main check and sync logic."""
        self.check_identity()
        
        modified_files = self.get_modified_files()
        ahead = self.is_ahead()

        if modified_files:
            current_time = time.time()
            last_mtime = self.get_latest_mtime(modified_files)
            
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
        elif ahead:
            logger.info("Local commits detected that are not on GitHub. Retrying push...")
            self.commit_and_push()
        else:
            self.pending_changes_since = None
            self.pull_changes()

    def commit_and_push(self):
        try:
            self.run_git(["add", "."])
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.run_git(["commit", "-m", f"Auto sync: {timestamp}"], check=False) # check=False in case no changes to commit
            
            self.pull_changes()
            
            logger.info("Pushing to remote...")
            self.run_git(["push"])
            logger.info("Push successful.")
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
    
    parser.add_argument("--non-interactive", action="store_true", help="Skip all input prompts (best for background/cron).")
    
    args = parser.parse_args()
    config = load_config()

    # Resolve Configuration
    repo_path = args.repo_path or config.get("repo_path")
    idle_threshold = args.idle_threshold or config.get("idle_threshold", 60)
    remote_url = config.get("remote_url")

    if not repo_path:
        if args.non_interactive:
            logger.error("No vault path configured and running in non-interactive mode. Exiting.")
            return
        
        print("--- Obsidian Git Sync Setup ---")
        while not repo_path:
            repo_path = input("Enter the absolute path to your Obsidian vault: ").strip()
            if not repo_path:
                print("Path cannot be empty.")
        
        if not remote_url:
            remote_url = input("Enter GitHub Remote URL (leave empty if already set): ").strip()
        
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
        if args.non_interactive:
            logger.error(f"{repo_path} is not a git repository. Cannot initialize in non-interactive mode.")
            return
            
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
