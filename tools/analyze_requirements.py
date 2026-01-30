#!/usr/bin/env python3
"""
DXVK Feature Requirements Analyzer

Parses DXVK source code to identify exactly which Vulkan features
are required for d3d9 support. Helps scope the MoltenVK patching work.

Usage:
    ./analyze_requirements.py [dxvk_path]
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# Features we're tracking
TRACKED_FEATURES = {
    # Extensions
    'VK_EXT_transform_feedback': 'Transform feedback (stream output)',
    'VK_EXT_robustness2': 'Robustness2 (null descriptors)',
    'VK_EXT_extended_dynamic_state': 'Extended dynamic state',
    'VK_EXT_vertex_attribute_divisor': 'Vertex attribute divisor',
    'VK_KHR_maintenance1': 'Maintenance1',
    'VK_KHR_maintenance2': 'Maintenance2', 
    'VK_KHR_maintenance3': 'Maintenance3',
    
    # Features
    'geometryShader': 'Geometry shaders',
    'tessellationShader': 'Tessellation shaders',
    'logicOp': 'Logic operations',
    'depthClamp': 'Depth clamping',
    'depthBiasClamp': 'Depth bias clamping',
    'fillModeNonSolid': 'Wireframe rendering',
    'samplerAnisotropy': 'Anisotropic filtering',
    'textureCompressionBC': 'BC texture compression',
    'independentBlend': 'Independent blend',
    'dualSrcBlend': 'Dual source blending',
    'multiViewport': 'Multiple viewports',
    'multiDrawIndirect': 'Multi-draw indirect',
    
    # Transform feedback specific
    'transformFeedback': 'Transform feedback feature',
    'geometryStreams': 'Geometry streams',
    
    # Robustness specific
    'nullDescriptor': 'Null descriptor',
    'robustBufferAccess': 'Robust buffer access',
}


def analyze_dxvk_d3d9(dxvk_path):
    """Analyze DXVK d3d9 source for Vulkan requirements."""
    d3d9_path = Path(dxvk_path) / 'src' / 'd3d9'
    
    if not d3d9_path.exists():
        print(f"Error: d3d9 source not found at {d3d9_path}")
        return None
    
    results = {
        'extensions_required': defaultdict(list),
        'features_required': defaultdict(list),
        'functions_used': defaultdict(list),
    }
    
    # Scan all source files
    for src_file in d3d9_path.glob('**/*.[ch]pp'):
        with open(src_file, 'r', errors='ignore') as f:
            content = f.read()
            filename = src_file.name
            
            # Check for extension usage
            for ext, desc in TRACKED_FEATURES.items():
                if ext.startswith('VK_'):
                    pattern = rf'\b{ext}\b'
                    if re.search(pattern, content):
                        results['extensions_required'][ext].append(filename)
                else:
                    # Feature flag
                    pattern = rf'\.{ext}\b|{ext}\s*='
                    if re.search(pattern, content):
                        results['features_required'][ext].append(filename)
            
            # Check for transform feedback functions
            xfb_funcs = [
                'vkCmdBeginTransformFeedback',
                'vkCmdEndTransformFeedback',
                'vkCmdBindTransformFeedbackBuffers',
                'vkCmdBeginQueryIndexed',
                'vkCmdEndQueryIndexed',
            ]
            for func in xfb_funcs:
                if func in content:
                    results['functions_used'][func].append(filename)
            
            # Check for geometry shader usage
            gs_patterns = [
                r'createGeometryShader',
                r'geometryShader',
                r'VK_SHADER_STAGE_GEOMETRY',
            ]
            for pattern in gs_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    results['functions_used']['geometry_shader_usage'].append(filename)
    
    return results


def print_report(results):
    """Print analysis report."""
    print("=" * 70)
    print("DXVK d3d9 Vulkan Requirements Analysis")
    print("=" * 70)
    
    print("\n## Required Extensions\n")
    if results['extensions_required']:
        for ext, files in sorted(results['extensions_required'].items()):
            desc = TRACKED_FEATURES.get(ext, 'Unknown')
            print(f"  {ext}")
            print(f"    Description: {desc}")
            print(f"    Used in: {', '.join(set(files))}")
            print()
    else:
        print("  None explicitly required")
    
    print("\n## Required Features\n")
    if results['features_required']:
        for feat, files in sorted(results['features_required'].items()):
            desc = TRACKED_FEATURES.get(feat, 'Unknown')
            print(f"  {feat}")
            print(f"    Description: {desc}")
            print(f"    Used in: {', '.join(set(files))}")
            print()
    else:
        print("  None explicitly required")
    
    print("\n## Vulkan Functions Used\n")
    if results['functions_used']:
        for func, files in sorted(results['functions_used'].items()):
            print(f"  {func}")
            print(f"    Used in: {', '.join(set(files))}")
            print()
    else:
        print("  None tracked")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY: What needs to be implemented in MoltenVK")
    print("=" * 70)
    
    critical = []
    if 'VK_EXT_transform_feedback' in results['extensions_required']:
        critical.append("Transform Feedback (VK_EXT_transform_feedback)")
    if 'geometryShader' in results['features_required']:
        critical.append("Geometry Shaders")
    if 'VK_EXT_robustness2' in results['extensions_required']:
        critical.append("Robustness2 / Null Descriptors")
    
    if critical:
        print("\nCritical missing features:")
        for c in critical:
            print(f"  ❌ {c}")
    else:
        print("\nNo critical missing features detected!")
    
    print()


def main():
    if len(sys.argv) > 1:
        dxvk_path = sys.argv[1]
    else:
        dxvk_path = os.environ.get('PROJECT_ROOT', '.') + '/DXVK'
    
    print(f"Analyzing DXVK at: {dxvk_path}")
    
    results = analyze_dxvk_d3d9(dxvk_path)
    if results:
        print_report(results)


if __name__ == '__main__':
    main()
