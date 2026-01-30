# MoltenVK + DXVK Insights

## Wine Version Matters

**Problem:** Wine 8.0.1 (CrossOver FOSS 23.7.1) has broken winevulkan that reports physical device Vulkan version as "0.0.0" instead of the actual version.

**Solution:** Use Wine 11.0+ which has updated winevulkan support.

```bash
brew install --cask wine-stable  # Installs Wine 11.0
```

## MoltenVK Feature Limitations

MoltenVK (Metal backend) does NOT support these Vulkan features that DXVK wants:

| Feature | Extension | Why Missing |
|---------|-----------|-------------|
| `geometryShader` | core | Metal has no geometry shaders |
| `shaderCullDistance` | core | Metal limitation |
| `depthClipEnable` | VK_EXT_depth_clip_enable | Not implemented |
| `robustBufferAccess2` | VK_EXT_robustness2 | Not implemented |
| `nullDescriptor` | VK_EXT_robustness2 | Not implemented |
| `khrPipelineLibrary` | VK_KHR_pipeline_library | Not implemented |

Verify with: `vulkaninfo 2>/dev/null | grep <feature_name>`

## D3D9 Doesn't Need All Features

Fallout New Vegas uses DirectX 9 with Shader Model 2.0:
- **No geometry shaders** - Introduced in DX10/SM4.0
- **No tessellation** - Introduced in DX11/SM5.0

Many DXVK "required" features are only needed for D3D10/11 games.

## DXVK Patching Strategy

To make DXVK work on MoltenVK, patch `src/dxvk/dxvk_device_info.cpp`:

1. **Bypass version check for Apple devices:**
```cpp
bool isAppleDevice = (m_properties.core.properties.vendorID == 0x106b);
if (isAppleDevice && m_properties.core.properties.apiVersion < DxvkVulkanApiVersion) {
  m_properties.core.properties.apiVersion = DxvkVulkanApiVersion;
}
```

2. **Change required features to optional:**
```cpp
ENABLE_FEATURE(core.features, geometryShader, false),  // was true
```

## Wine Prefix Architecture

For 32-bit games like FNV on Wine64:
- 64-bit DLLs go in `system32/`
- 32-bit DLLs go in `syswow64/`

DXVK d3d9.dll (32-bit) must be in `syswow64/` for FNV to find it.

## DLL Override

Set native d3d9 override:
```bash
WINEPREFIX=/path/to/prefix wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\DllOverrides" /v d3d9 /t REG_SZ /d native /f
```

## Known Issues

### Visual Flickering
Likely caused by:
1. Missing `nullDescriptor` - unbound texture access undefined
2. Missing `depthClipEnable` - depth clipping semantics differ
3. Missing robustness features - OOB access returns garbage

### Potential Fixes to Investigate
1. DXVK config options for workarounds
2. Older DXVK versions with fewer requirements
3. MoltenVK patches to add missing features
4. Shader patching to avoid problematic code paths

## Useful Debug Environment Variables

```bash
# DXVK logging
DXVK_LOG_LEVEL=debug
DXVK_LOG_PATH=/path/to/logs

# MoltenVK logging
MVK_CONFIG_LOG_LEVEL=3
MVK_CONFIG_DEBUG=1

# Wine debug
WINEDEBUG=+loaddll
```
