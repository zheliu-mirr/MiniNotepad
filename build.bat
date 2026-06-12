@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   MiniNotepad Build Script
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.8+
    pause
    exit /b 1
)

echo [1/3] Installing PyInstaller...
pip install pyinstaller -q

if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "MiniNotepad.spec" del /q MiniNotepad.spec

echo [2/3] Building EXE...
pyinstaller --noconfirm --onefile --windowed --name MiniNotepad --clean --collect-all tkinter mininotepad.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo EXE: dist\MiniNotepad.exe
echo.

if exist "dist\MiniNotepad.exe" (
    for %%A in ("dist\MiniNotepad.exe") do echo Size: %%~zA bytes
)

pause