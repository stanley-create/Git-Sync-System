@echo off
title Obsidian Git Sync
:menu
cls
echo ========================================
echo        Obsidian Git Sync System
echo ========================================
echo 1. Start Syncing
echo 2. Fix Network (Clear Git Proxy)
echo 3. Repair Connection (Full)
echo 4. Exit
echo ========================================
set /p choice="Choose an option (1-4): "

if "%choice%"=="1" goto start_sync
if "%choice%"=="2" goto fix_network
if "%choice%"=="3" goto full_repair
if "%choice%"=="4" exit
goto menu

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
