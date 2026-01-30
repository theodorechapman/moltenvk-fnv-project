#!/bin/bash
set -e

PROJECT_ROOT="$HOME/Coding/moltenvk-fnv-project"
echo "Setting up MoltenVK FNV development environment at $PROJECT_ROOT"

# Create directory structure
mkdir -p "$PROJECT_ROOT"/{build,tests,tools,captures,logs}
mkdir -p "$PROJECT_ROOT"/tests/{unit,integration,reference}
mkdir -p "$PROJECT_ROOT"/build/{moltenvk,dxvk,tests}

cd "$PROJECT_ROOT"

# ============================================
# 1. Install dependencies via Homebrew
# ============================================
echo "Installing dependencies..."
brew install \
    cmake \
    ninja \
    meson \
    python3 \
    glslang \
    spirv-tools \
    mingw-w64 \
    wine-stable \
    molten-vk \
    vulkan-headers \
    vulkan-loader \
    vulkan-tools

# ============================================
# 2. Clone repositories
# ============================================
echo "Cloning repositories..."

# MoltenVK - your fork
if [ ! -d "MoltenVK" ]; then
    git clone https://github.com/KhronosGroup/MoltenVK.git
    cd MoltenVK
    # Fetch the geometry shader PR for reference
    git fetch origin pull/1815/head:geometry-shaders
    cd ..
fi

# DXVK - upstream (has d3d9, unlike the macOS fork)
if [ ! -d "DXVK" ]; then
    git clone https://github.com/doitsujin/dxvk.git DXVK
fi

# SPIRV-Cross (for shader debugging)
if [ ! -d "SPIRV-Cross" ]; then
    git clone https://github.com/KhronosGroup/SPIRV-Cross.git
fi

# ============================================
# 3. Build MoltenVK
# ============================================
echo "Building MoltenVK..."
cd "$PROJECT_ROOT/MoltenVK"
./fetchDependencies --macos
make macos

# Create symlink to built library
ln -sf "$PROJECT_ROOT/MoltenVK/Package/Latest/MoltenVK/dylib/macOS/libMoltenVK.dylib" \
       "$PROJECT_ROOT/build/moltenvk/"

cd "$PROJECT_ROOT"

# ============================================
# 4. Build DXVK with d3d9 for macOS
# ============================================
echo "Building DXVK..."
cd "$PROJECT_ROOT/DXVK"

# Create macOS cross-compile file
cat > build-macos.txt << 'EOF'
[binaries]
c = 'x86_64-w64-mingw32-gcc'
cpp = 'x86_64-w64-mingw32-g++'
ar = 'x86_64-w64-mingw32-ar'
strip = 'x86_64-w64-mingw32-strip'
windres = 'x86_64-w64-mingw32-windres'

[properties]
needs_exe_wrapper = true

[host_machine]
system = 'windows'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF

# Build DXVK (this will likely fail initially - that's expected)
meson setup --cross-file build-macos.txt --buildtype release build.64 || true
cd build.64
ninja || echo "DXVK build failed - expected, we'll fix this iteratively"

cd "$PROJECT_ROOT"

# ============================================
# 5. Set up Wine prefix
# ============================================
echo "Setting up Wine prefix..."
export WINEPREFIX="$HOME/.wine-fnv-mo2"
export WINEARCH=win64

# Initialize prefix (skip if already exists)
if [ ! -d "$WINEPREFIX" ]; then
    wineboot --init
else
    echo "Wine prefix already exists at $WINEPREFIX"
fi

echo ""
echo "============================================"
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy Fallout New Vegas to: $WINEPREFIX/drive_c/Games/FNV/"
echo "2. Run: source env.sh"
echo "3. Run: make test-vulkan  (to verify Vulkan works)"
echo "4. Run: make run-fnv      (to capture first errors)"
echo "============================================"
