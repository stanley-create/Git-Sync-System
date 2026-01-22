import os
import time
import subprocess
import argparse
import datetime
import sys
import json

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
                print(f"[{timestamp}] Push failed.")
        else:
             print(f"[{timestamp}] Changes detected. Waiting for idle... ({int(idle_time)}/{int(idle_threshold)}s)", end='\r')
    else:
        run_git_command(["git", "pull", "--rebase"], repo_path)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")

def setup_wizard():
    print("--- Obsidian Git Sync Setup ---")
    repo_path = input("Enter the absolute path to your Obsidian vault: ").strip()
    
    # Validate path
    while not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"Error: '{repo_path}' is not a valid git repository (missing .git folder).")
        repo_path = input("Please enter a valid path: ").strip()

    idle_threshold = input("Enter idle threshold in seconds (default 60): ").strip()
    idle_threshold = int(idle_threshold) if idle_threshold.isdigit() else 60
    
    interval = input("Enter check interval in seconds (default 10): ").strip()
    interval = int(interval) if interval.isdigit() else 10

    config = {
        "repo_path": repo_path,
        "idle_threshold": idle_threshold,
        "interval": interval
    }
    save_config(config)
    return config

def main():
    parser = argparse.ArgumentParser(description="Auto-sync Obsidian vault with GitHub.")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup wizard.")
    parser.add_argument("repo_path", nargs="?", help="Path to the Obsidian vault.")
    parser.add_argument("--idle_threshold", type=int, help="Seconds of inactivity before syncing.")
    parser.add_argument("--interval", type=int, help="Interval (seconds) to check for changes.")
    
    args = parser.parse_args()

    # Load config
    config = load_config()

    if args.setup:
        config = setup_wizard()
    
    # Priority: Args > Config > Defaults
    repo_path = args.repo_path or config.get("repo_path")
    idle_threshold = args.idle_threshold or config.get("idle_threshold", 60)
    interval = args.interval or config.get("interval", 10)

    if not repo_path:
        print("Error: No repository path provided.")
        print("Run with --setup to configure, or provide path as argument.")
        return
    
    repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"Error: {repo_path} is not a valid git repository.")
        return

    print(f"Monitoring {repo_path}")
    print(f"Idle threshold: {idle_threshold}s")
    print(f"Check interval: {interval}s")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            sync_repo(repo_path, idle_threshold)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping auto-sync.")

if __name__ == "__main__":
    main()
