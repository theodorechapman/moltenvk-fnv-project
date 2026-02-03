# Technical Insights - MoltenVK + DXVK + Wine

## MoltenVK/Metal Limitations

### Unsupported Vulkan Features
These features must be disabled in DXVK for MoltenVK compatibility:
- `geometryShader` - Not needed for D3D9, safe to disable
- `shaderCullDistance` - Metal doesn't support cull distance
- `depthClipEnable` - VK_EXT_depth_clip_enable not available
- `robustBufferAccess2` - Falls back to shader-level bounds checking
- `nullDescriptor` - Must use valid descriptors for all slots
- `khrPipelineLibrary` - Graphics pipeline library not supported

### Metal Binding Index Constraint
**Critical**: Metal doesn't allow two resources at the same binding index.

DXVK's D3D9 implementation reuses binding indices for color and depth textures. The fix requires:
1. Add `DepthImage` binding type to `DxsoBindingType` enum
2. Double the texture slot layout: `[CB][ColorTex][DepthTex]`
3. Update `computeResourceSlotId()` to handle new layout
4. Bind textures to both color and depth slots when binding
5. Update hardcoded binding numbers in GLSL shaders

### Primitive Restart
Metal always has primitive restart enabled - it cannot be disabled. Enable primitive restart for all D3D9 topologies. This is safe because D3D9 doesn't use restart indices (0xFFFF/0xFFFFFFFF).

### DrawIndex/gl_DrawID
MoltenVK doesn't support `gl_DrawID` (SPIR-V `DrawIndex` builtin). This breaks DXVK's text-based HUD rendering. Only graph-based HUD elements (like `frametimes`) work.

## Wine/winevulkan Quirks

### Vulkan Version Reporting
winevulkan reports Vulkan API version as 0.0.0 for Apple devices, even though MoltenVK supports 1.3+. Workaround: detect Apple vendor ID (0x106b) and force correct version.

### File Path Mapping
Windows paths in Wine map to the prefix:
- `C:\file.dat` → `wine-prefix/drive_c/file.dat`
- Use this for cross-process communication between Wine and macOS

## DXVK Build System

### Cross-Compilation
DXVK is cross-compiled for Windows using mingw32 (`i686-w64-mingw32-g++`). Use Windows APIs (`windows.h`, `CreateFileA`, `MapViewOfFile`) not POSIX (`sys/mman.h`, `mmap`).

### Conditional Compilation
Use `#ifdef _WIN32` for Windows-specific code paths. The POSIX path (`#else`) is only for native Linux/macOS builds, which isn't the normal use case.

## Performance Monitoring

### Shared Memory Approach
For external monitoring tools, use memory-mapped files:
1. DXVK creates file via Windows API (`CreateFileA`, `CreateFileMappingA`)
2. File appears in Wine prefix on macOS
3. Python/native app mmaps the same file for reading
4. Use `FlushViewOfFile` to ensure data visibility

### Key Metrics to Track
- Frame time in microseconds (more precise than FPS)
- Draw calls (indexed vs non-indexed, instanced)
- Command buffer submissions (high count = overhead)
- Shader/pipeline compilation (per-frame vs total)
- Present mode and swapchain info

## Debugging Tips

### DXVK Environment Variables
- `DXVK_LOG_LEVEL=debug` - Verbose logging
- `DXVK_HUD=frametimes` - Only graph works on MoltenVK
- `DXVK_LOG_PATH=/path` - Log file location

### MoltenVK Environment Variables
- `MVK_CONFIG_LOG_LEVEL=2` - Info level logging
- `MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1` - Required for descriptor indexing
- `MVK_ALLOW_METAL_FENCES=1` - Enable Metal fences
- `MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0` - Async queue submits

### Common Errors
- "DrawIndex is not supported in MSL" → gl_DrawID used, can't fix easily
- "SPIR-V to MSL conversion error" → Check for unsupported features
- Version 0.0.0 errors → Apply Apple vendor ID workaround

## D3D9 Specifics

### Texture Stage Binding Layout
With MoltenVK patches, the binding layout per shader stage is:
```
[0..CBCount-1]                        = Constant buffers
[CBCount..CBCount+MaxTex-1]           = Color/regular images
[CBCount+MaxTex..CBCount+2*MaxTex-1]  = Depth/shadow images
```

### Present Interval
- `D3DPRESENT_INTERVAL_DEFAULT` (0) → treated as 1 (vsync ON)
- `D3DPRESENT_INTERVAL_IMMEDIATE` (0x80000000) → 0 (vsync OFF)
- Can override with `d3d9.presentInterval` in dxvk.conf

## Potential Stutter Causes (Hypotheses)

1. **Double texture binding overhead** - Every bind does 2x work
2. **Shader bounds checking** - Without robustness2, adds conditional branches
3. **Frame pacing** - Present mode selection or sync issues
4. **Descriptor update frequency** - More descriptors = more updates
5. **Pipeline state changes** - Not compilation, but switching

## Files to Watch

### DXVK
- `src/dxvk/dxvk_device_info.cpp` - Feature flags and device detection
- `src/dxso/dxso_util.h` - Binding slot calculation
- `src/dxso/dxso_compiler.cpp` - Shader compilation, bounds checking
- `src/d3d9/d3d9_device.cpp` - Draw call implementation
- `src/d3d9/d3d9_swapchain.cpp` - Present implementation

### Shaders
- `src/d3d9/shaders/d3d9_fixed_function_*.glsl` - Hardcoded binding numbers
