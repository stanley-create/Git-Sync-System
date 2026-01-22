@echo off
title Obsidian Git Sync
echo Starting Obsidian Git Sync...
echo.
python sync.py
if %errorlevel% neq 0 (
    echo.
    echo Script crashed or exited with an error.
    echo TIP: If this is a connection issue, try running: python sync.py --repair
    pause
)
