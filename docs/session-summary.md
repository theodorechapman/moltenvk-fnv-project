# Session Summary - January 30, 2026

## Major Breakthrough: Fallout New Vegas Running on MoltenVK/DXVK

The game successfully launches and runs with DXVK on MoltenVK via Wine 11. Visual flickering issues remain to be fixed.

## What Was Accomplished

### 1. Wine 11.0 Installed
- Wine 8.0.1 (CrossOver) had broken winevulkan - reported device as version "0.0.0"
- Wine 11.0 stable installed via Homebrew: `brew install --cask wine-stable`
- Wine 11 correctly reports MoltenVK's Vulkan 1.4.334 support

### 2. Wine Prefix Created
- Location: `wine-prefix-11/` in project directory
- Contains Steam + Fallout New Vegas copied from previous prefix
- DXVK d3d9.dll installed to `syswow64/` (for 32-bit games)

### 3. DXVK Patched for MoltenVK Compatibility
Multiple patches to `DXVK/src/dxvk/dxvk_device_info.cpp`:

**Apple Device Version Workaround** (lines 92-97):
```cpp
// MoltenVK/Apple workaround: winevulkan reports device version as 0.0.0
// but MoltenVK actually supports Vulkan 1.3+. Apple vendor ID is 0x106b.
bool isAppleDevice = (m_properties.core.properties.vendorID == 0x106b);
if (isAppleDevice && m_properties.core.properties.apiVersion < DxvkVulkanApiVersion) {
  m_properties.core.properties.apiVersion = DxvkVulkanApiVersion;
}
```

**Disabled Required Features** (MoltenVK doesn't support these):
- `geometryShader` - line 761: changed `true` to `false`
- `shaderCullDistance` - line 773: changed `true` to `false`
- `depthClipEnable` (extDepthClipEnable) - line 852: changed `true` to `false`
- `robustBufferAccess2` (extRobustness2) - line 902: changed `true` to `false`
- `nullDescriptor` (extRobustness2) - line 904: changed `true` to `false`
- `khrPipelineLibrary` - line 943: changed `true` to `false`

### 4. Makefile Updated
- `make run` - Rebuilds DXVK, installs to Wine prefix, runs game via NVSE
- `make dxvk` - Just rebuilds and installs DXVK
- WINEPREFIX now points to `wine-prefix-11/`

## Current State

**Working:**
- Game launcher opens and detects GPU
- Game loads saves
- 3D rendering works

**Issues:**
- Visual flickering during loading
- Bright flashes during gameplay
- Frame flickering

## Likely Causes of Flickering

1. **Missing `nullDescriptor`** - DXVK uses this for unbound textures/buffers. Without it, accessing unbound resources may cause visual glitches.

2. **Missing `depthClipEnable`** - D3D9 has specific depth clipping semantics. The comment in DXVK says "Depth clip matches D3D semantics where depth clamp does not"

3. **Missing `robustBufferAccess2`** - Out-of-bounds buffer reads may return garbage instead of zeros

## Next Steps

1. **Investigate flickering** - Enable DXVK debug logging to see what's happening
2. **Try DXVK config options** - There may be workarounds for missing features
3. **Consider older DXVK version** - Older versions may have fewer feature requirements
4. **Research MoltenVK patches** - Some features might be implementable

## Key Files Modified

- `DXVK/src/dxvk/dxvk_device_info.cpp` - Feature requirements
- `Makefile` - Build and run targets
- `wine-prefix-11/drive_c/windows/syswow64/d3d9.dll` - Patched DXVK DLL
- `wine-prefix-11/drive_c/Games/Steam/steamapps/common/Fallout New Vegas/dxvk.conf` - DXVK config

## Commands

```bash
# Rebuild and run
make run

# Just rebuild DXVK
make dxvk

# Check MoltenVK feature support
vulkaninfo 2>/dev/null | grep -E "geometryShader|nullDescriptor|robustBuffer"
```
