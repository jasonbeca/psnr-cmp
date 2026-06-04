#!/bin/bash
set -e

# =============================================================================
# VidCompare Pro - Intelligent CentOS 7 Build Script (Root)
# =============================================================================
# Usage: ./build-centos.sh
# Pre-requisite: The 'dist/centos' folder must contain the offline dependencies.
# =============================================================================

WORK_DIR=$(pwd)
DIST_LIB="$WORK_DIR/dist/centos"
WHEELS_DIR="$DIST_LIB/wheels"
# Source is CURRENT DIRECTORY (Root)
SRC_DIR="$WORK_DIR"
ENV_PREFIX="$DIST_LIB/env"

echo "========================================"
echo "   VidCompare Pro - CentOS 7 Builder"
echo "========================================"

# --- 1. Check Offline Resources ---
if [ ! -d "$DIST_LIB" ]; then
    echo "❌ Error: Offline dependencies not found in '$DIST_LIB'!"
    echo "Please upload 'dist/centos' folder (with wheels & miniconda) to your server."
    exit 1
fi

MINICONDA_INSTALLER=$(find "$DIST_LIB" -maxdepth 1 -name "Miniconda3*.sh" | head -n 1)
if [ -z "$MINICONDA_INSTALLER" ]; then
    echo "❌ Error: Miniconda installer missing in dist/centos!"
    exit 1
fi

# --- 2. Setup Python Environment ---
echo "🚀 [1/5] Setting up isolated Python environment..."
# Create environment inside dist/centos/env to keep root clean
if [ ! -d "$ENV_PREFIX" ]; then
    bash "$MINICONDA_INSTALLER" -b -p "$ENV_PREFIX"
fi
source "$ENV_PREFIX/bin/activate"

# --- 3. Install Dependencies ---
echo "🚀 [2/5] Installing dependencies..."
# Install from local wheels
pip install "$WHEELS_DIR"/*.whl --no-index --find-links "$WHEELS_DIR" --force-reinstall

# --- 4. Prepare Build Workspace ---
echo "🚀 [3/5] Preparing workspace (auto-patching)..."
if [ -d "build_centos_tmp" ]; then rm -rf "build_centos_tmp"; fi
mkdir "build_centos_tmp"

# Copy source code (exclude known large/garbage dirs to speed up)
# Using rsync if available, else cp
echo "   Copying source..."
# Copy core folders
cp -r core ui utils main.py icon.png icon.ico build_centos_tmp/

# Setup FFmpeg
FFMPEG_ARCHIVE=$(find "$DIST_LIB" -maxdepth 1 -name "ffmpeg-*-static.tar.xz" | head -n 1)
if [ ! -z "$FFMPEG_ARCHIVE" ]; then
    echo "   Injecting FFmpeg..."
    tar -xf "$FFMPEG_ARCHIVE" -C build_centos_tmp
    
    # Move binaries to root of build_tmp
    FFMPEG_SUBDIR=$(find build_centos_tmp -maxdepth 1 -name "ffmpeg-*-static" -type d | head -n 1)
    if [ ! -z "$FFMPEG_SUBDIR" ]; then
        mv "$FFMPEG_SUBDIR/ffmpeg" build_centos_tmp/
        mv "$FFMPEG_SUBDIR/ffprobe" build_centos_tmp/
        rm -rf "$FFMPEG_SUBDIR"
    fi
fi

# ⚠️ INTELLIGENT PATCHING: PyQt6 -> PyQt5 ⚠️
echo "   🔧 Auto-patching source for CentOS 7 compatibility..."
cd build_centos_tmp

# Replace Imports
grep -rl "PyQt6" . | xargs sed -i 's/PyQt6/PyQt5/g'

# Replace Enums (Qt6 scopedenums -> Qt5 global enums)
grep -rl "Qt\." . | xargs sed -i 's/Qt\.Orientation\./Qt./g'
grep -rl "Qt\." . | xargs sed -i 's/Qt\.AlignmentFlag\./Qt./g'
grep -rl "Qt\." . | xargs sed -i 's/Qt\.MouseButton\./Qt./g'
grep -rl "Qt\." . | xargs sed -i 's/Qt\.GlobalColor\./Qt./g'
grep -rl "Qt\." . | xargs sed -i 's/Qt\.BrushStyle\./Qt./g'
grep -rl "Qt\." . | xargs sed -i 's/Qt\.ScrollBarPolicy\./Qt./g'
grep -rl "Qt\." . | xargs sed -i 's/Qt\.AspectRatioMode\./Qt./g'

# --- 5. Build Binary ---
echo "🚀 [4/5] Compiling Binary..."
pyinstaller --clean --noconfirm --onefile --windowed \
    --name "VidCompare_Linux" \
    --add-binary "ffmpeg:." \
    --add-binary "ffprobe:." \
    --hidden-import "PIL" \
    --hidden-import "PyQt5" \
    --hidden-import "numpy" \
    main.py

# --- 6. Finalize ---
echo "🚀 [5/5] Finalizing..."
cd "$WORK_DIR"
if [ ! -d "dist/linux_output" ]; then mkdir -p "dist/linux_output"; fi

if [ -f "build_centos_tmp/dist/VidCompare_Linux" ]; then
    mv build_centos_tmp/dist/VidCompare_Linux dist/linux_output/
    rm -rf build_centos_tmp
    echo "========================================"
    echo "✅ SUCCESS! Binary created at:"
    echo "   $WORK_DIR/dist/linux_output/VidCompare_Linux"
    echo "========================================"
else
    echo "❌ Build Failed!"
    exit 1
fi
