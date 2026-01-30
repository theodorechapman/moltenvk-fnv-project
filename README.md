# MoltenVK Patching for Fallout: New Vegas

A test-driven development project to add missing Vulkan features to MoltenVK, enabling DXVK's d3d9 backend to run Fallout: New Vegas on macOS.

## Quick Start

```bash
# 1. Run the setup script
chmod +x setup.sh
./setup.sh

# 2. Fallout New Vegas should be installed via Steam at:
# ~/.wine-fnv-mo2/drive_c/Games/Steam/steamapps/common/Fallout New Vegas/

# 3. Load the environment
source env.sh

# 4. Run the first test
make test-vulkan

# 5. Try to run FNV (it will fail - that's expected!)
make run-fnv-debug

# 6. Analyze what's broken
python3 tools/capture.py analyze
```

## Development Workflow

### The TDD Loop

```
┌─────────────────────────────────────────────────────────────┐
│  1. Run FNV → 2. Capture Error → 3. Write Test →           │
│                                                             │
│  4. Implement Fix → 5. Run Test → 6. Run FNV → Repeat      │
└─────────────────────────────────────────────────────────────┘
```

### Daily Workflow

```bash
# Morning: See where we are
source env.sh
python3 tools/capture.py progress

# Identify the next issue
python3 tools/capture.py next

# Write a minimal test for that issue
vim tests/unit/test_<feature>.c

# Implement the fix in MoltenVK
vim MoltenVK/MoltenVK/GPUObjects/MVK<something>.mm

# Build and test
make build-mvk
make test-unit

# Try FNV again
make run-fnv-debug

# Analyze results
python3 tools/capture.py analyze

# Commit your progress
git add -A && git commit -m "Implement <feature>"
```

## Project Structure

```
~/Coding/moltenvk-fnv-project/
├── MoltenVK/              # Your fork - THIS IS WHERE YOU CODE
├── DXVK/                  # DXVK source (mostly reference)
├── tests/
│   ├── unit/              # Minimal Vulkan tests
│   │   ├── test_xfb.c     # Transform feedback tests
│   │   ├── test_gs.c      # Geometry shader tests
│   │   └── test_robustness.c
│   └── integration/       # Full app tests
├── tools/
│   ├── capture.py         # Error capture/analysis
│   └── compare.py         # Visual comparison
├── logs/                  # Runtime logs
├── Makefile               # Main build orchestration
├── env.sh                 # Environment setup
└── progress.json          # Your progress over time

Wine prefix: ~/.wine-fnv-mo2/
├── drive_c/Games/Steam/steamapps/common/Fallout New Vegas/  # Game installation
└── drive_c/MO2/           # Mod Organizer 2 (for mod management)
```

## Key Make Targets

| Target | Description |
|--------|-------------|
| `make build-mvk` | Build MoltenVK |
| `make build-dxvk` | Build DXVK |
| `make test-vulkan` | Verify Vulkan works |
| `make test-xfb` | Run transform feedback tests |
| `make test-gs` | Run geometry shader tests |
| `make run-fnv` | Run Fallout New Vegas |
| `make run-fnv-debug` | Run with extra debugging |
| `make run-fnv-nvse` | Run with NVSE (for mods) |
| `make run-fnv-nvse-debug` | Run with NVSE + debugging |
| `make diagnose` | Show current blockers |
| `make errors` | Show errors from logs |
| `make iterate` | Full rebuild + test cycle |

## Features to Implement

### Priority 1: Transform Feedback (VK_EXT_transform_feedback)

This is the main blocker. DXVK d3d9 uses it for stream output.

**Files to modify:**
- `MoltenVK/MoltenVK/GPUObjects/MVKPipeline.mm`
- `MoltenVK/MoltenVK/Commands/MVKCmdDraw.mm`
- `MoltenVK/MoltenVK/GPUObjects/MVKBuffer.mm`

**Approach:**
1. Advertise the extension
2. Modify vertex shaders to write outputs to a storage buffer
3. Implement buffer binding for XFB
4. Implement queries for primitives written

**Reference:** Look at Ryujinx's implementation for Switch emulation.

### Priority 2: Geometry Shaders

PR #1815 has partial work. You may be able to build on it.

**Files to modify:**
- `MoltenVK/MoltenVK/GPUObjects/MVKPipeline.mm`
- SPIRV-Cross (for shader translation)

**Approach:**
- Emulate GS using Metal mesh shaders or compute + vertex

### Priority 3: Robustness2 (nullDescriptor)

DXVK uses null descriptors for unbound texture slots.

**Files to modify:**
- `MoltenVK/MoltenVK/GPUObjects/MVKDescriptor.mm`

## Debugging Tips

### Enable All Logging

```bash
export MVK_CONFIG_LOG_LEVEL=3
export MVK_CONFIG_DEBUG=1
export MVK_CONFIG_TRACE_VULKAN_CALLS=2
export VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation
export DXVK_LOG_LEVEL=trace
```

### Capture Metal Frames

1. Open Xcode
2. Debug → Attach to Process → wine64
3. Debug → Capture GPU Workload

### View Shader Translation

```bash
# Dump SPIR-V to file
export MVK_CONFIG_SHADER_DUMP_DIR=/tmp/shaders

# Then inspect with spirv-cross
spirv-cross --output shader.msl /tmp/shaders/shader.spv
```

### Compare Against Linux

Run the same test on Linux with a real Vulkan driver to get reference output:
```bash
# On Linux
./test_xfb > reference_output.txt

# Compare
diff reference_output.txt macos_output.txt
```

## Common Issues

### "Extension not supported"
MoltenVK doesn't advertise the extension. Add it to the supported list and implement the functions.

### "Shader compilation failed"
SPIRV-Cross couldn't translate the shader to MSL. Check the SPIR-V input and MSL output.

### "Pipeline creation failed"
Usually a missing feature in the pipeline state. Check which feature is being requested.

### "Device lost"
Something crashed in Metal. Enable Metal validation for more details:
```bash
export MTL_DEBUG_LAYER=1
export MTL_SHADER_VALIDATION=1
```

## Resources

- [MoltenVK Source](https://github.com/KhronosGroup/MoltenVK)
- [DXVK Source](https://github.com/doitsujin/dxvk)
- [Vulkan Spec](https://registry.khronos.org/vulkan/specs/1.3/html/)
- [Metal Shading Language Spec](https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf)
- [Transform Feedback Extension](https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_EXT_transform_feedback.html)

## Progress Tracking

Run `python3 tools/capture.py progress` to see your progress over time.

The goal is to get the error count to zero, one category at a time!

## Contributing Back

Once you get things working, please contribute your changes back:

1. Fork MoltenVK on GitHub
2. Create a feature branch
3. Submit a PR with your changes
4. The community will thank you!
