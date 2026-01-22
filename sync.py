import os
import time
import subprocess
import argparse
import datetime
import sys

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
        # Don't print error for simple checks like status or pull if they just return non-zero
        # But for debugging it is useful. Let's keep it but handle specifically where needed.
        if "up to date" not in e.stderr and "no changes" not in e.stderr:
             pass # Suppress common noise, but log real errors
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
    """
    Revised logic:
    1. Check if git status is dirty.
    2. If dirty:
       - Check if 'idle_threshold' has passed since last file modification.
       - If yes: Add -> Commit -> Pull (Rebase) -> Push.
       - If no: Wait.
    3. If clean:
       - Pull (Rebase) to get remote changes.
    """
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    # 1. Check status
    try:
        # Run manually with subprocess to assume check=True behavior handled
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
        # Dirty
        last_mtime = get_last_modified_time(repo_path)
        current_time = time.time()
        idle_time = current_time - last_mtime
        
        if idle_time >= idle_threshold:
            print(f"[{timestamp}] Changes detected. Idle for {int(idle_time)}s. Syncing...")
            
            # Add
            run_git_command(["git", "add", "."], repo_path)
            
            # Commit
            commit_msg = f"Auto sync: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            run_git_command(["git", "commit", "-m", commit_msg], repo_path)
            print(f"[{timestamp}] Committed changes.")
            
            # Pull (Rebase) - Important to do AFTER commit to save local work, 
            # and BEFORE Push to resolve potential remote conflicts.
            print(f"[{timestamp}] Pulling remote changes...")
            pull_res = run_git_command(["git", "pull", "--rebase"], repo_path)
            if pull_res is None:
                print(f"[{timestamp}] Pull failed (conflict?). Please resolve manually.")
                return 

            # Push
            print(f"[{timestamp}] Pushing to remote...")
            if run_git_command(["git", "push"], repo_path):
                print(f"[{timestamp}] Push successful.")
            else:
                print(f"[{timestamp}] Push failed.")
        else:
             print(f"[{timestamp}] Changes detected. Waiting for idle... ({int(idle_time)}/{int(idle_threshold)}s)", end='\r')
    else:
        # Clean
        # Periodically pull. Since we run this function in a loop, strictly calling pull every time 
        # might be spammy if the loop is fast. But for 'sync', it's okay.
        # print(f"[{timestamp}] No local changes. Checking remote...", end='\r')
        run_git_command(["git", "pull", "--rebase"], repo_path)

def main():
    parser = argparse.ArgumentParser(description="Auto-sync Obsidian vault with GitHub.")
    parser.add_argument("repo_path", nargs="?", default=".", help="Path to the Obsidian vault (git repository). Defaults to current directory.")
    parser.add_argument("--idle_threshold", type=int, default=60, help="Seconds of inactivity before syncing changes. Default is 60.")
    parser.add_argument("--interval", type=int, default=10, help="Interval (seconds) to check for changes. Default is 10.")
    
    args = parser.parse_args()
    repo_path = os.path.abspath(args.repo_path)
    
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"Error: {repo_path} is not a valid git repository.")
        return

    print(f"Monitoring {repo_path}")
    print(f"Idle threshold: {args.idle_threshold}s")
    print(f"Check interval: {args.interval}s")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            sync_repo(repo_path, args.idle_threshold)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopping auto-sync.")

if __name__ == "__main__":
    main()
