@echo off
setlocal
echo ========================================================
echo   VidCompare Pro - CentOS 7 Offline Package Generator
echo ========================================================

set "DIST_DIR=dist\centos"
set "SRC_DEST=%DIST_DIR%\psnr-cmp"

:: 1. Check if Offline dependencies exist
if not exist "%DIST_DIR%\Miniconda3*.sh" (
    echo [ERROR] Miniconda installer missing in %DIST_DIR%
    pause
    exit /b 1
)

:: 2. Create/Clean Destination Source Dir
echo [1/3] Preparing source directory...
if exist "%SRC_DEST%" (
    rmdir /s /q "%SRC_DEST%"
)
mkdir "%SRC_DEST%"

:: 3. Copy Source Code (Excluding giant folders)
echo [2/3] Copying project source code...
xcopy "core" "%SRC_DEST%\core" /E /I /Q
xcopy "ui" "%SRC_DEST%\ui" /E /I /Q
xcopy "utils" "%SRC_DEST%\utils" /E /I /Q
copy "main.py" "%SRC_DEST%\"
copy "requirements.txt" "%SRC_DEST%\"
copy "icon.png" "%SRC_DEST%\"
copy "icon.ico" "%SRC_DEST%\"

:: 4. Final Instructions
echo [3/3] Package ready!
echo.
echo ========================================================
echo   SUCCESS!
echo   The folder 'dist\centos' is now self-contained.
echo.
echo   [NEXT STEPS]
echo   1. Zip the 'dist\centos' folder.
echo   2. Upload it to your CentOS 7 server.
echo   3. Run 'bash build.sh' inside the folder.
echo ========================================================
pause
