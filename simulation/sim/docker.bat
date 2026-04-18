@echo off
setlocal enabledelayedexpansion

::Pobierz literę dysku i resztę ścieżki osobno
set "DRIVE_LETTER=%~d0"
set "FOLDER_PATH=%~p0"

::Zamień wielką literę dysku na małą
set "DRIVE_LETTER=!DRIVE_LETTER:~0,1!"
for %%i in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
    set "DRIVE_LETTER=!DRIVE_LETTER:%%i=%%i!"
)

set "LOWER_DRIVE=!DRIVE_LETTER!"
if "!LOWER_DRIVE!"=="C" set "LOWER_DRIVE=c"
if "!LOWER_DRIVE!"=="D" set "LOWER_DRIVE=d"

::Budujemy ścieżkę WSL: zamieniamy \ na /
set "FIXED_PATH=!FOLDER_PATH:\=/!"

::Składamy wszystko w całość: /mnt/ + mała_litera + ścieżka
set "WSL_PATH=/mnt/!LOWER_DRIVE!!FIXED_PATH!"

:: Usuń ostatni ukośnik
if "!WSL_PATH:~-1!"=="/" set "WSL_PATH=!WSL_PATH:~0,-1!"

pip install roslibpy PyQt6
start /B python ../app/gui.py

echo Uruchamianie w: !WSL_PATH!
wsl -d Ubuntu -e bash -c "cd '!WSL_PATH!' && docker compose up --build"

pause