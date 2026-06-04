@echo off
REM One-click Windows build to binary (output: dist\windows)

setlocal

set PYTHON=py -3
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    set PYTHON=python
)

%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3 is required.
    exit /b 1
)

if not exist ".env_win\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON% -m venv .env_win
)

echo Installing dependencies...
.env_win\Scripts\python.exe -m pip install --upgrade pip
.env_win\Scripts\python.exe -m pip install -r requirements.txt
.env_win\Scripts\python.exe -m pip install pyinstaller pillow

set ROOT_DIR=%CD%

if not exist "%ROOT_DIR%\\icon.png" (
    echo ERROR: icon.png not found!
    exit /b 1
)

echo Cleaning previous build output...
if exist "build\windows" rmdir /s /q "build\windows"
if exist "dist\windows" rmdir /s /q "dist\windows"

echo Building with PyInstaller...
.env_win\Scripts\pyinstaller.exe --clean ^
    --onedir ^
    --windowed ^
    --name "VidCompare-Pro" ^
    --icon "%ROOT_DIR%\\icon.png" ^
    --add-data "%ROOT_DIR%\\icon.png;." ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module IPython ^
    --exclude-module notebook ^
    --distpath "dist\windows" ^
    --workpath "build\windows" ^
    --specpath "build\windows" ^
    "%ROOT_DIR%\\main.py"

echo.
echo Build completed: dist\windows\VidCompare-Pro
endlocal
