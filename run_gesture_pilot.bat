@echo off
title GesturePilot-C
echo Starting GesturePilot-C Environment...
cd /d "%~dp0"

if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
    echo Activating venv and installing dependencies...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r scripts/requirements.txt
) else (
    call venv\Scripts\activate.bat
    echo Updating dependencies...
    pip install -r scripts/requirements.txt
)

if not exist "build\Debug\gesturepilot.exe" (
    echo Executable not found. Building the project now...
    if not exist "build" mkdir build
    cd build
    cmake ..
    cmake --build .
    cd ..
)

echo.
echo ==========================================================
echo  GesturePilot-C is Running!
echo.
echo  - A camera window should appear shortly.
echo  - Point your index finger to move the mouse.
echo  - Pinch your index and thumb together to click and drag.
echo  - Make sure your hand is visible in the camera view.
echo.
echo  To exit:
echo  1. Click on the camera window and press 'q'
echo  2. OR press Ctrl+C in this console window.
echo ==========================================================
echo.

.\build\Debug\gesturepilot.exe
pause
