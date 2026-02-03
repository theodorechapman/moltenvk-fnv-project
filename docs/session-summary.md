# Session Summary - February 2, 2026

## Project Overview

Running Fallout New Vegas on macOS using:
- **Wine 11** (translation layer)
- **DXVK** (D3D9 → Vulkan)
- **MoltenVK** (Vulkan → Metal)

### Test Environment
- **Hardware**: M4 Pro MacBook Pro, 48GB RAM
- **Game Settings**: 1920x1080, Ultra, Windowed mode

## Current State

### What's Working
- Game launches and is playable
- Faster load times than wined3d
- No visual bugs in windowed mode
- Shader compilation is fine (only noticed single stutter when opening settings first time)
- Menu mouse behavior normal with v-sync disabled

### What's Broken
1. **Consistent stuttering** - Occurs when panning camera or walking. Also visible in animated objects (windmill). Not related to area loading or shader compilation.
2. **Fullscreen flickering** - Black flickers and visual bugs in fullscreen mode
3. **Menu mouse with v-sync** - Mouse skips around in menus when v-sync enabled

## Repository Structure

| Component | Upstream | Commit | Modified |
|-----------|----------|--------|----------|
| DXVK | doitsujin/dxvk | `4bbe4879` | Yes - `8b3a564b` |
| MoltenVK | KhronosGroup/MoltenVK | `f79c6c56` | No |
| SPIRV-Cross | KhronosGroup/SPIRV-Cross | `a0fba56c` | No |

These are standalone git clones (not submodules) listed in `.gitignore`.

## DXVK Patches Applied

Full patch at `docs/dxvk-moltenvk-full.patch` (400 lines, 8 files).

### Summary of Changes

**Disabled Vulkan Features** (MoltenVK doesn't support):
- `geometryShader` - not needed for D3D9
- `shaderCullDistance`
- `depthClipEnable`
- `robustBufferAccess2`
- `nullDescriptor`
- `khrPipelineLibrary`

**Apple Device Workaround** (`dxvk_device_info.cpp`):
- winevulkan reports Vulkan version as 0.0.0 on Apple devices
- Added detection for Apple vendor ID (0x106b) to force correct version

**Metal Binding Compatibility** (`dxso_util.h`, `dxso_compiler.cpp`, `d3d9_fixed_function.cpp`, `d3d9_device.cpp`):
- Metal doesn't allow two resources at the same binding index
- Added separate `DepthImage` binding type
- Doubled texture slot layout (color + depth bindings)
- Updated all binding numbers in shaders accordingly

**Primitive Restart** (`d3d9_util.cpp`):
- Metal always has primitive restart enabled and cannot disable it
- Changed all D3D9 primitive topologies to enable primitive restart
- Safe because D3D9 doesn't use restart indices (0xFFFF/0xFFFFFFFF)

## New Features Added This Session

### Performance Monitoring System

Created a comprehensive performance monitoring system with DXVK hooks and a Python GUI.

**Files created:**
- `DXVK/src/dxvk/dxvk_perf_monitor.h` - Shared memory structure and monitor singleton
- `tools/perf_monitor.py` - Python GUI for real-time monitoring

**Files modified:**
- `DXVK/src/d3d9/d3d9_device.cpp` - Initialize monitor, hook draw calls
- `DXVK/src/d3d9/d3d9_swapchain.cpp` - Hook frame begin/end on Present()

**How it works:**
1. DXVK creates a memory-mapped file at `C:\dxvk_perf.dat` (Wine path)
2. This maps to `wine-prefix-11/drive_c/dxvk_perf.dat` on macOS
3. Python app reads this file and displays real-time stats

**Data exported:**
- Frame time (current, min, max, average) in microseconds
- FPS (instant and rolling average)
- Draw calls (total, indexed, instanced)
- Primitive count
- Command buffer submissions
- Shaders/pipelines compiled (per-frame and total)
- GPU memory stats
- Swapchain info (resolution, present mode)
- 300-frame history ring buffer

**Makefile targets:**
- `make perf-monitor` - Run the performance monitor GUI
- `make perf-monitor-log` - Run with CSV logging

### DXVK HUD Limitation Discovered

The DXVK HUD text rendering uses `gl_DrawID` which MoltenVK doesn't support:
```
[mvk-error] SPIR-V to MSL conversion error: DrawIndex is not supported in MSL.
```

Only the `frametimes` graph works (no text). Added `make run-hud` target that uses only frametimes.

## Stuttering Investigation

### Exploration Findings

**Frame Pacing** (`dxvk_presenter.cpp`):
- DXVK uses Vulkan present modes (FIFO, MAILBOX, IMMEDIATE, FIFO_RELAXED)
- Key config options: `dxvk.tearFree`, `dxvk.latencySleep`, `d3d9.presentInterval`
- MoltenVK supports `VK_KHR_present_wait2` which DXVK uses for frame pacing

**nullDescriptor Fallback** (`dxso_compiler.cpp`):
- Without `nullDescriptor`, DXVK adds manual bounds checking in shaders
- Extra branching: `ULessThan`, `CompositeConstruct`, `Select` operations
- This affects relative constant buffer indexing

**Double Texture Binding Overhead**:
- The MoltenVK patch doubles texture bindings (color + depth slots)
- Every texture bind now binds to 2 slots
- This is a significant per-frame overhead

### Hypotheses for Stuttering

1. **Frame pacing issue** - Present mode or sync problems
2. **Disabled `nullDescriptor`** - Shader bounds checking overhead
3. **Disabled `depthClipEnable`** - Depth clipping semantics differences
4. **Double texture binding** - Per-frame descriptor binding overhead
5. **Pipeline state changes** - Not shader compilation, but pipeline switches

## Key Makefile Targets

```bash
make run          # Rebuild DXVK + launch game with NVSE
make run-hud      # Run with DXVK HUD (frametimes graph only)
make run-vd       # Run in Wine virtual desktop
make perf-monitor # Run performance monitor GUI
make dxvk         # Just rebuild DXVK
make clear        # Kill Wine processes
```

## Next Steps

1. **Use performance monitor** to identify exact stutter source:
   - Run `make perf-monitor` in one terminal
   - Run `make run` in another
   - Observe frame time spikes and correlate with draw calls/submissions

2. **Potential fixes based on findings:**
   - If high submissions → batch command buffers
   - If draw call spikes → investigate state changes
   - If consistent overhead → optimize double texture binding (only bind depth when needed)

3. **Frame pacing investigation:**
   - Test with `dxvk.tearFree = False`
   - Test with `d3d9.maxFrameRate` limiter
   - Check if `VK_PRESENT_MODE_MAILBOX_KHR` helps

4. **Profile with Metal System Trace** if needed for deeper GPU analysis

## Configuration Files

**dxvk.conf** (in game directory) - Current effective config:
```
dxvk.tearFree = True
d3d9.invariantPosition = True
d3d9.floatEmulation = Strict
d3d9.deferSurfaceCreation = True
d3d9.hideNvidiaGpu = True
d3d9.presentInterval = 1
d3d9.maxFrameLatency = 1
d3d9.numBackBuffers = 3
```

## Important Notes

- DXVK is cross-compiled for Windows using mingw32 - use Windows APIs, not POSIX
- The game uses `nvse_loader.exe` (New Vegas Script Extender)
- Wine prefix is at `wine-prefix-11/`
- Game directory: `wine-prefix-11/drive_c/Games/Steam/steamapps/common/Fallout New Vegas`
