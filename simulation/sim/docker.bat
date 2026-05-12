@echo off
setlocal enabledelayedexpansion

echo Checking if Docker is running...

tasklist | findstr /i "Docker Desktop.exe" >nul
if %errorlevel%==0 (
    echo Docker Desktop is already running.
    goto docker_wait
)

echo Launching Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

:docker_wait
echo Waiting for Docker backend...

:wait
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" info >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 >nul
    goto wait
)

echo Docker is ready.

:: Get drive letter and path separately
set "DRIVE_LETTER=%~d0"
set "FOLDER_PATH=%~p0"

:: Convert drive letter to lowercase
set "DRIVE_LETTER=!DRIVE_LETTER:~0,1!"
for %%i in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
    set "DRIVE_LETTER=!DRIVE_LETTER:%%i=%%i!"
)

set "LOWER_DRIVE=!DRIVE_LETTER!"
if "!LOWER_DRIVE!"=="C" set "LOWER_DRIVE=c"
if "!LOWER_DRIVE!"=="D" set "LOWER_DRIVE=d"

:: Build WSL path: convert backslash to forward slash
set "FIXED_PATH=!FOLDER_PATH:\=/!"

:: Combine everything: /mnt/ + lowercase_letter + path
set "WSL_PATH=/mnt/!LOWER_DRIVE!!FIXED_PATH!"

:: Remove the last slash
if "!WSL_PATH:~-1!"=="/" set "WSL_PATH=!WSL_PATH:~0,-1!"

echo Running in: !WSL_PATH!
wsl -d Ubuntu -e bash -c "cd '!WSL_PATH!' && docker compose up --build"

pause