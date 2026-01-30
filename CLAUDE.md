# MoltenVK + DXVK + Fallout New Vegas Project

## Project Goal
Run Fallout New Vegas on macOS using DXVK (D3D9→Vulkan) + MoltenVK (Vulkan→Metal) + Wine 11.

## Current Status
Game runs but has visual flickering. See `docs/session-summary.md` for details.

## Key Commands
- `make run` - Rebuild DXVK and launch game
- `make dxvk` - Just rebuild DXVK

## Key Files
- `DXVK/src/dxvk/dxvk_device_info.cpp` - Patched for MoltenVK (see `docs/dxvk-moltenvk.patch`)
- `wine-prefix-11/` - Wine 11 prefix with game
- `docs/insights.md` - Technical learnings
- `docs/session-summary.md` - Session progress

## Next Task
Fix visual flickering - likely caused by disabled `nullDescriptor` and `depthClipEnable` features.

---

*BASH*

IMPORTANT: Avoid commands that cause output buffering issues

DO NOT pipe output through head, tail, less, or more when monitoring or checking command output
DO NOT use | head -n X or | tail -n X to truncate output - these cause buffering problems
Instead, let commands complete fully, or use --max-lines flags if the command supports them
For log monitoring, prefer reading files directly rather than piping through filters

When checking command output:

Run commands directly without pipes when possible
If you need to limit output, use command-specific flags (e.g., git log -n 10 instead of git log | head -10)
Avoid chained pipes that can cause output to buffer indefinitely

*PYTHON*

Use uv for all package management and running programs