@echo off
title Obsidian Git Sync

if "%~1"=="--silent" goto start_sync_silent

:menu
cls
echo ========================================
echo        Obsidian Git Sync System
echo ========================================
echo 1. Start Syncing (Default in 5s)
echo 2. Fix Network (Clear Git Proxy)
echo 3. Repair Connection (Full)
echo 4. Exit
echo ========================================
choice /c 1234 /t 5 /d 1 /n /m "Choose an option (1-4): "

if errorlevel 4 exit
if errorlevel 3 goto full_repair
if errorlevel 2 goto fix_network
if errorlevel 1 goto start_sync

:fix_network
echo Clearing Git proxy settings...
git config --global --unset http.proxy
git config --global --unset https.proxy
echo Done.
pause
goto menu

:full_repair
echo Running full repair...
python sync.py --repair
pause
goto menu

:start_sync_silent
echo Running in silent background mode...
python sync.py --non-interactive
exit /b

:start_sync
echo Starting Obsidian Git Sync...
echo.
python sync.py
if %errorlevel% neq 0 (
    echo.
    echo Script crashed or exited with an error.
    echo TIP: Use Option 2 or 3 in the menu to fix connection issues.
    pause
)
goto menu
