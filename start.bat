@echo off
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if exist config.json (
    python sync.py
) else (
    echo Configuration not found. Starting setup...
    python sync.py --setup
)

pause
