@echo off
title Obsidian Git Sync
echo Starting Obsidian Git Sync...
echo.
python sync.py
if %errorlevel% neq 0 (
    echo.
    echo Script crashed or exited with an error.
    pause
)
