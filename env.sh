#!/bin/bash
# Source this file: source env.sh

export PROJECT_ROOT="$HOME/Coding/moltenvk-fnv-project"
export WINEPREFIX="$HOME/.wine-fnv-mo2"
export WINEARCH=win64

# Point Wine to our custom MoltenVK
export MVK_CONFIG_LOG_LEVEL=2
export MVK_CONFIG_DEBUG=1
export MVK_CONFIG_TRACE_VULKAN_CALLS=1

# Vulkan configuration
export VK_ICD_FILENAMES="$PROJECT_ROOT/build/moltenvk/MoltenVK_icd.json"
export VK_LAYER_PATH="/usr/local/share/vulkan/explicit_layer.d"
export VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation"

# DXVK configuration
export DXVK_LOG_LEVEL=debug
export DXVK_LOG_PATH="$PROJECT_ROOT/logs"
export DXVK_HUD=full

# Wine DLL overrides - use DXVK
export WINEDLLOVERRIDES="d3d9=n,b;d3d11=n,b;dxgi=n,b"

# Convenience aliases
alias build-mvk="cd $PROJECT_ROOT/MoltenVK && make macos && cd -"
alias build-dxvk="cd $PROJECT_ROOT/DXVK/build.64 && ninja && cd -"
alias run-fnv="cd $PROJECT_ROOT && make run-fnv"
alias run-fnv-nvse="cd $PROJECT_ROOT && make run-fnv-nvse"
alias tail-logs="tail -f $PROJECT_ROOT/logs/*.log"

# Helper functions
function mvk-log() {
    cat "$PROJECT_ROOT/logs/moltenvk.log" | grep -E "(ERROR|WARN|$1)"
}

function dxvk-log() {
    cat "$PROJECT_ROOT/logs/FalloutNV_d3d9.log" 2>/dev/null || \
    cat "$PROJECT_ROOT/logs/"*d3d9.log 2>/dev/null || \
    echo "No DXVK logs found"
}

function capture-frame() {
    # Trigger Metal frame capture
    export MTL_CAPTURE_ENABLED=1
    export METAL_CAPTURE_ENABLED=1
    echo "Metal capture enabled. Run your app and press Cmd+Shift+C in Xcode"
}

echo "Environment loaded. Key commands:"
echo "  build-mvk   - Rebuild MoltenVK"
echo "  build-dxvk  - Rebuild DXVK"
echo "  run-fnv     - Run Fallout New Vegas"
echo "  tail-logs   - Follow log files"
echo "  mvk-log     - View MoltenVK errors"
echo "  dxvk-log    - View DXVK errors"
