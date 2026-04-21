@echo off
setlocal enabledelayedexpansion

echo Launching Docker engine...
wsl -d Ubuntu -u root -e service docker start >nul 2>&1

echo Docker has started.

set "DRIVE_LETTER=%~d0"
set "FOLDER_PATH=%~p0"

set "DRIVE_LETTER=!DRIVE_LETTER:~0,1!"
for %%i in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
    set "DRIVE_LETTER=!DRIVE_LETTER:%%i=%%i!"
)

set "LOWER_DRIVE=!DRIVE_LETTER!"
if "!LOWER_DRIVE!"=="C" set "LOWER_DRIVE=c"
if "!LOWER_DRIVE!"=="D" set "LOWER_DRIVE=d"

set "FIXED_PATH=!FOLDER_PATH:\=/!"

set "WSL_PATH=/mnt/!LOWER_DRIVE!!FIXED_PATH!"

if "!WSL_PATH:~-1!"=="/" set "WSL_PATH=!WSL_PATH:~0,-1!"

echo Launching in: !WSL_PATH!
wsl -d Ubuntu -e bash -c "cd '!WSL_PATH!' && docker compose down && docker compose up --build"

pause