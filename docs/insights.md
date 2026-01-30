# Insights - MoltenVK FNV Project

## Wine Version Compatibility

### Critical Finding
**Wine 8.0.1 (CrossOver FOSS 23.7.1) has broken winevulkan support for Vulkan 1.3+**

When DXVK queries the Vulkan device through Wine's winevulkan.dll, it reports:
```
Found device: Apple M4 Pro ( 0.0.0)
Skipping: Device does not support Vulkan 1.3
```

The "0.0.0" version indicates winevulkan isn't properly translating the Vulkan API version from MoltenVK (which supports 1.4.334) to the Windows application.

**Solution**: Use Wine 11.0+ which has updated winevulkan support.

## 32-bit vs 64-bit Games

### Important
Fallout: New Vegas is a **32-bit game**. This means:
- DXVK DLLs must be compiled with `i686-w64-mingw32-gcc` (not x86_64)
- DLLs go in `syswow64/` directory (not `system32/`)
- Check game architecture with: `file /path/to/game.exe`

## DXVK Version Requirements

| DXVK Version | Vulkan Requirement |
|--------------|-------------------|
| 1.x (up to 1.10.3) | Vulkan 1.2 |
| 2.x (2.0+) | Vulkan 1.3 |

If stuck with Vulkan 1.2, use DXVK 1.10.3, but note it may have compilation issues with GCC 15+ (missing `#include <cstdint>`).

## MoltenVK Vulkan Support Timeline

| MoltenVK Version | Vulkan Support | Release Date |
|------------------|----------------|--------------|
| 1.2.x | Vulkan 1.2 | Pre-2025 |
| 1.3 | Vulkan 1.3 | May 2025 |
| 1.4 | Vulkan 1.4 | August 2025 |

## WineD3D as Fallback

WineD3D (Wine's built-in D3D→OpenGL translation) works well on macOS via Apple's OpenGL-to-Metal layer. For games that don't need cutting-edge features, this path is often more stable than DXVK on macOS.

**Detection**: Look for `wined3d` messages in Wine logs:
```
fixme:d3d:wined3d_guess_card_vendor Received unrecognized GL_VENDOR "Apple"
```

## Cross-Compilation on Apple Silicon

When building Windows DLLs on Apple Silicon Mac:
1. Use Homebrew's mingw-w64: `brew install mingw-w64`
2. For 32-bit: `i686-w64-mingw32-gcc`
3. For 64-bit: `x86_64-w64-mingw32-gcc`
4. Vulkan headers: Add `-I/opt/homebrew/include` to compiler flags

## MoltenVK ICD Configuration

The ICD JSON file uses relative paths:
```json
{
    "ICD": {
        "library_path": "./libMoltenVK.dylib",
        "api_version": "1.2.0"
    }
}
```

Keep `libMoltenVK.dylib` in the same directory as the JSON file, then set:
```bash
export VK_ICD_FILENAMES="/path/to/MoltenVK_icd.json"
```

## Steam Games in Wine

Steam games require Steam to be running in the Wine prefix before launching:
```bash
WINEPREFIX="/path/to/prefix" wine64 "/path/to/Steam/steam.exe" -silent &
sleep 15  # Wait for Steam to initialize
```

Otherwise you'll get "Application Load Error" from the game.

## NVSE (Script Extender) Requirements

NVSE must be launched from the game directory:
```bash
cd "/path/to/Fallout New Vegas"
wine64 nvse_loader.exe
```

Running from a different directory causes "Couldn't find FalloutNV.exe" error.
