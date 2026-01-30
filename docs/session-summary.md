# Session Summary - MoltenVK FNV Project Setup

## Date: 2026-01-30

## Overview

This session focused on setting up a development environment to run Fallout: New Vegas on macOS using DXVK (D3D9→Vulkan translation) and MoltenVK (Vulkan→Metal translation). The goal was to establish a TDD workflow for adding missing Vulkan features to MoltenVK.

## What Was Accomplished

### 1. Path Configuration
All Wine prefix paths were updated to point to the user's existing Wine prefix:
- **Wine Prefix**: `/Users/theo/.wine-fnv-mo2/`
- **FNV Location**: `~/.wine-fnv-mo2/drive_c/Games/Steam/steamapps/common/Fallout New Vegas/`
- **MO2 Location**: `~/.wine-fnv-mo2/drive_c/MO2/`

Files updated:
- `Makefile` - `WINEPREFIX` and `FNV_DIR` variables
- `env.sh` - Environment exports
- `setup.sh` - Setup script paths
- `tools/capture.py` - Python path references
- `README.md` - Documentation

### 2. Dependencies Installed
Via Homebrew:
- cmake, ninja, meson, python3
- glslang, spirv-tools
- mingw-w64 (for cross-compiling DXVK)
- molten-vk, vulkan-headers, vulkan-loader, vulkan-tools

### 3. MoltenVK Built
- Cloned from KhronosGroup/MoltenVK
- Version: **v1.4.1** (supports Vulkan 1.4.334)
- Built for macOS using `make macos`
- Library copied to `build/moltenvk/libMoltenVK.dylib`

### 4. DXVK Built
- Both 32-bit and 64-bit versions built
- Version: **2.7.1**
- 32-bit DLLs installed to Wine prefix's `syswow64/` directory
- 64-bit DLLs installed to `system32/` directory

### 5. New Make Targets Added
- `make run-fnv-nvse` - Run FNV with NVSE (for mods)
- `make run-fnv-nvse-debug` - Run with NVSE + debugging

## Current State & Blocking Issue

### The Problem
DXVK 2.7.1 requires Vulkan 1.3, and while MoltenVK 1.4.2 supports Vulkan 1.4.334, **Wine's winevulkan.dll reports the device as version "0.0.0"**.

```
info:  Found device: Apple M4 Pro ( 0.0.0)
info:    Skipping: Device does not support Vulkan 1.3
warn:  DXVK: No adapters found. A Vulkan 1.3 capable setup is required.
```

### Root Cause
The user has **Wine 8.0.1 (CrossOver FOSS 23.7.1)** which has an older winevulkan implementation that doesn't properly expose Vulkan 1.3+ API versions from the host MoltenVK to Windows applications.

### Workaround That Works
**WineD3D works perfectly!** When DXVK isn't loaded, Wine uses its built-in WineD3D which translates D3D9→OpenGL→Metal (via Apple's OpenGL-to-Metal layer). The game runs with no visual bugs using this path.

## Next Steps for Future Sessions

### Option 1: Upgrade Wine (Recommended)
Install Wine 11.0 from Homebrew which has proper winevulkan support for Vulkan 1.3+:
```bash
brew install --cask wine-stable
```
Then use the new Wine binary explicitly instead of the CrossOver symlink.

### Option 2: Use WineD3D
The game works fine with WineD3D. If DXVK isn't strictly needed, this is a valid solution.

### Option 3: Debug winevulkan
Investigate why Wine 8.0.1's winevulkan reports device version as 0.0.0 and potentially patch it.

## Key Files & Locations

| Item | Location |
|------|----------|
| Project Root | `/Users/theo/Coding/moltenvk-fnv-project/` |
| Wine Prefix | `/Users/theo/.wine-fnv-mo2/` |
| MoltenVK Source | `./MoltenVK/` |
| MoltenVK Library | `./build/moltenvk/libMoltenVK.dylib` |
| DXVK Source | `./DXVK/` |
| DXVK 32-bit Build | `./DXVK/build.32/` |
| DXVK 64-bit Build | `./DXVK/build.64/` |
| FNV Executable | Wine prefix + `drive_c/Games/Steam/steamapps/common/Fallout New Vegas/FalloutNV.exe` |
| NVSE Loader | Same directory + `nvse_loader.exe` |

## Technical Details

### Game Architecture
- **Fallout: New Vegas** is a **32-bit** game (PE32 Intel 80386)
- Uses DirectX 9 for graphics
- Has NVSE (New Vegas Script Extender) installed
- Managed with Mod Organizer 2 (MO2)

### Translation Paths
1. **DXVK Path** (not working due to Wine version):
   ```
   D3D9 → DXVK → Vulkan → winevulkan.dll → MoltenVK → Metal
   ```

2. **WineD3D Path** (working):
   ```
   D3D9 → WineD3D → OpenGL → Apple OpenGL-to-Metal → Metal
   ```

### Wine Binary Location
```
/opt/homebrew/bin/wine64 -> /Applications/Wine Crossover.app/Contents/Resources/wine/bin/wine64
```

## Commands for Testing

```bash
# Load environment
source env.sh

# Test Vulkan (native)
VK_ICD_FILENAMES="$PWD/build/moltenvk/MoltenVK_icd.json" vulkaninfo --summary

# Run FNV with NVSE (uses WineD3D currently)
make run-fnv-nvse

# Run FNV with debugging
make run-fnv-nvse-debug
```

## Environment Variables for DXVK

When Wine's winevulkan is fixed, these should work:
```bash
WINEPREFIX="/Users/theo/.wine-fnv-mo2"
VK_ICD_FILENAMES="/Users/theo/Coding/moltenvk-fnv-project/build/moltenvk/MoltenVK_icd.json"
WINEDLLOVERRIDES="d3d9=n,b;dxgi=n,b"
MVK_CONFIG_LOG_LEVEL=2
DXVK_LOG_LEVEL=info
```
