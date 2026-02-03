# DXVK + MoltenVK Optimization Plan for Fallout: New Vegas

## Current Status

**Problem**: Consistent rhythmic stuttering (0.33-0.5s intervals) and low FPS (17-22 fps)

**Root Cause Identified**: CS chunk execution spikes up to **229ms** in `dxvk_cs.cpp`

**Translation Stack Overhead**:
```
x86 Game Code
    ↓ Rosetta 2 (~20% overhead)
Windows API calls
    ↓ Wine
macOS API calls + DirectX 9
    ↓ DXVK
Vulkan commands
    ↓ MoltenVK
Metal commands
    ↓
Apple Silicon GPU
```

## Research Findings

### 1. MoltenVK Configuration Issues

| Setting | Default | Recommended | Impact |
|---------|---------|-------------|--------|
| `MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS` | 1 | 1 (required) | DXVK needs this for sampler arrays |
| `MVK_CONFIG_SHOULD_MAXIMIZE_CONCURRENT_COMPILATION` | 0 | **1** | Parallel shader compilation |
| `MVK_CONFIG_FAST_MATH_ENABLED` | 2 | 1 | Faster shaders |
| `MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS` | 1 | **0** | Async queue submission |
| `MVK_ALLOW_METAL_FENCES` | 0 | 1 | Better sync performance |

### 2. Wine Synchronization

**MSync (Mach Semaphore Synchronization)** provides native macOS sync:
- Uses Mach semaphores instead of eventfd
- Uncontended waits happen in user-space
- No file descriptor limitations
- Enable with: `WINEMSYNC=1`

### 3. Pipeline Compilation Stalls

MoltenVK pipeline compilation takes **~15ms per state change**. This explains:
- 229ms spikes = multiple pipeline compilations in one chunk
- Rhythmic stuttering = periodic state changes triggering recompilation

**Solutions**:
1. Dynamic state to reduce recompilation
2. Pipeline caching (already enabled)
3. Concurrent compilation (enable via config)

### 4. Command Encoding Overhead

`vkQueueSubmit` takes **5.8ms on M1** vs 0.06ms on Intel/Windows.

For draw-call bound apps, **80% of frame time** can be encoding commands.

## Optimization Strategy

### Phase 1: Configuration Tuning (No Code Changes)

Test these configurations in order:

```bash
# 1. Try MSync first
make run-msync

# 2. Try all optimizations
make run-optimized

# 3. Capture detailed performance logs
make run-perflog
```

### Phase 2: Comprehensive Logging

Add timing to identify slow Vulkan calls:

```bash
# Full call tracing (slow, but reveals bottlenecks)
make run-trace
```

Analyze the trace for:
- Calls taking >5ms
- Pattern of slow calls (every N frames?)
- Which Vulkan functions are slowest

### Phase 3: DXVK Code Optimizations

Based on CS chunk timing we added, investigate:

1. **Command batching**: Are we flushing too often?
   - File: `DXVK/src/d3d9/d3d9_device.cpp`
   - Look for `FlushImplicit()` calls

2. **State tracking**: Are we setting redundant state?
   - File: `DXVK/src/d3d9/d3d9_stateblock.cpp`
   - Compare previous vs current state before applying

3. **Resource uploads**: Are staging buffers causing stalls?
   - Already increased to 32MB
   - Consider double-buffering

### Phase 4: MoltenVK Code Optimizations

If DXVK isn't the bottleneck, look at MoltenVK:

1. **Pipeline compilation**:
   - File: `MoltenVK/MoltenVK/GPUObjects/MVKPipeline.mm`
   - Look for synchronous MTLLibrary creation

2. **Command encoding**:
   - File: `MoltenVK/MoltenVK/Commands/MVKCommandBuffer.mm`
   - Profile Metal encoder creation

3. **Resource management**:
   - File: `MoltenVK/MoltenVK/GPUObjects/MVKBuffer.mm`
   - Check for implicit GPU syncs

## Test Targets

| Target | Purpose |
|--------|---------|
| `make run` | Standard run with current optimizations |
| `make run-msync` | Test MSync synchronization |
| `make run-optimized` | All optimizations enabled |
| `make run-trace` | Full Vulkan call tracing |
| `make run-perflog` | Performance stats logging |
| `make profile-quick` | 10s Metal System Trace |
| `make profile-cpu` | CPU Time Profiler |

## Metrics to Track

1. **Frame time variance**: Target <5ms variance
2. **CS chunk execution**: Target <10ms per chunk
3. **Pipeline compilations**: Should be 0 during gameplay
4. **Staging buffer reallocations**: Should be 0 during gameplay

## References

- [MoltenVK Config Parameters](https://github.com/KhronosGroup/MoltenVK/blob/main/Docs/MoltenVK_Configuration_Parameters.md)
- [DXVK-macOS Fork](https://github.com/Gcenx/DXVK-macOS)
- [Wine MSync](https://github.com/marzent/wine-msync)
- [MoltenVK Issue #2530](https://github.com/KhronosGroup/MoltenVK/issues/2530) - Argument buffer perf regression
- [MoltenVK Discussion #1789](https://github.com/KhronosGroup/MoltenVK/discussions/1789) - Pipeline compilation

## Code Changes Made

### DXVK Modifications

1. **Increased descriptor pool size** (`dxvk_descriptor_pool.cpp`):
   - MaxSets: 1024 → 8192
   - Pool sizes increased proportionally

2. **Increased staging buffer** (`d3d9_device.h`):
   - StagingBufferSize: 4MB → 32MB

3. **Added CS chunk timing** (`dxvk_cs.cpp`):
   - Logs chunks taking >5ms

4. **Added frame sync timing** (`d3d9_swapchain.cpp`):
   - Logs SyncFrameLatency waits >20ms

5. **Added present timing** (`dxvk_presenter.cpp`):
   - Logs vkQueuePresentKHR >20ms

## Next Steps

1. Run `make run-msync` and report if stuttering improves
2. Run `make run-optimized` for maximum optimization
3. If still stuttering, run `make run-trace` and analyze slow calls
4. Based on findings, target specific code for optimization
