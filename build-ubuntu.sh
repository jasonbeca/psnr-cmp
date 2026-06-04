#!/bin/bash
# One-click Ubuntu build to binary (output: dist/ubuntu)

set -e

ENV_DIR=".env_ubuntu"

python3 --version >/dev/null 2>&1 || { echo "ERROR: Python 3 is required."; exit 1; }

if [ ! -d "$ENV_DIR" ]; then
    echo "Creating virtual environment at $ENV_DIR..."
    python3 -m venv "$ENV_DIR"
fi

echo "Activating virtual environment..."
source "$ENV_DIR/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller pillow

if [ ! -f "icon.png" ]; then
    echo "ERROR: icon.png not found!"
    exit 1
fi

echo "Cleaning previous build output..."
rm -rf build/ubuntu dist/ubuntu

ROOT_DIR="$(pwd)"

echo "Building with PyInstaller..."
pyinstaller --clean \
    --onedir \
    --windowed \
    --name "VidCompare-Pro" \
    --icon "${ROOT_DIR}/icon.png" \
    --add-data "${ROOT_DIR}/icon.png:." \
    --exclude-module matplotlib \
    --exclude-module scipy \
    --exclude-module pandas \
    --exclude-module IPython \
    --exclude-module notebook \
    --distpath "dist/ubuntu" \
    --workpath "build/ubuntu" \
    --specpath "build/ubuntu" \
    "${ROOT_DIR}/main.py"

echo ""
echo "Build completed: dist/ubuntu/VidCompare-Pro"
