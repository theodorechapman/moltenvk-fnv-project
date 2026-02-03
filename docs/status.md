# Fallout New Vegas on macOS - Status

## Overview

Running Fallout New Vegas on macOS using:
- **Wine 11** (translation layer)
- **DXVK** (D3D9 → Vulkan)
- **MoltenVK** (Vulkan → Metal)

## Test Environment

- **Hardware**: M4 Pro MacBook Pro, 48GB RAM
- **Game Settings**: 1920x1080, Ultra, Windowed mode
- **V-Sync**: Disabled (improves menu mouse behavior)

## Current State

### Working

- Game launches and is playable
- **Faster load times** than wined3d
- **No visual bugs** in windowed mode (wined3d had some quirks)
- Shader compilation is fine - only noticed single compile stutter when opening settings for the first time
- Menu mouse behavior is normal with v-sync disabled

### Broken

| Issue | Severity | Notes |
|-------|----------|-------|
| **Consistent stuttering** | High | Occurs when panning camera or walking. Also visible in animated objects (windmill). Not related to area loading or shader compilation. |
| **Fullscreen flickering** | Medium | Black flickers and visual bugs in fullscreen mode. Fills screen correctly but rendering is broken. |
| **Menu mouse with v-sync** | Low | Mouse skips around in menus when v-sync enabled. Needs more testing to confirm. |

## DXVK Patches Applied

See `docs/dxvk-moltenvk-full.patch` for complete diff against upstream `4bbe4879`.

### Summary of Changes

**Disabled Vulkan Features** (MoltenVK doesn't support):
- `geometryShader` - not needed for D3D9
- `shaderCullDistance`
- `depthClipEnable`
- `robustBufferAccess2`
- `nullDescriptor`
- `khrPipelineLibrary`

**Apple Device Workaround**:
- winevulkan reports Vulkan version as 0.0.0 on Apple devices
- Added detection for Apple vendor ID (0x106b) to force correct version

**Metal Binding Compatibility**:
- Metal doesn't allow two resources at the same binding index
- Added separate `DepthImage` binding type
- Doubled texture slot layout (color + depth bindings)
- Updated all binding numbers in shaders accordingly

**Primitive Restart**:
- Metal always has primitive restart enabled and cannot disable it
- Changed all D3D9 primitive topologies to enable primitive restart
- Safe because D3D9 doesn't use restart indices (0xFFFF/0xFFFFFFFF)

## Hypotheses for Stuttering

1. **Frame pacing issue** - Could be related to present mode or sync between Metal and game loop

2. **Disabled `nullDescriptor`** - DXVK may rely on this for unbound texture slots. When disabled, accessing unbound slots could cause issues.

3. **Disabled `depthClipEnable`** - Depth clipping semantics differ between D3D and Vulkan. Disabling this might cause incorrect depth behavior requiring fallback paths.

4. **Double texture binding overhead** - Binding every texture to both color and depth slots doubles the binding work. May be causing per-frame overhead.

5. **Pipeline compilation** - Even though shader compilation seems fine, pipeline state changes might be causing stalls (different from shader compilation).

## Next Steps

- [ ] Profile with Metal System Trace to identify where time is spent
- [ ] Test with MVK_CONFIG_LOG_LEVEL to see MoltenVK debug output
- [ ] Try reducing texture bindings (only bind to depth slot when actually needed)
- [ ] Investigate frame pacing / present mode options
- [ ] Test on simpler scenes to isolate the stutter source

## Repository Info

| Component | Upstream | Commit | Modified |
|-----------|----------|--------|----------|
| DXVK | doitsujin/dxvk | `4bbe4879` | Yes |
| MoltenVK | KhronosGroup/MoltenVK | `f79c6c56` | No |
| SPIRV-Cross | KhronosGroup/SPIRV-Cross | `a0fba56c` | No |
