#!/usr/bin/env python3
"""Graph and analyze DXVK vs WineD3D benchmark results."""

import json
import sys
import os

# Use matplotlib with Agg backend for headless operation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def load_benchmark(filepath):
    with open(filepath) as f:
        return json.load(f)

def analyze_and_graph(dxvk_path, wined3d_path, output_dir):
    dxvk = load_benchmark(dxvk_path)
    wined3d = load_benchmark(wined3d_path)

    # Extract time series
    dxvk_times = [s['time'] for s in dxvk['samples']]
    dxvk_cpu = [s['cpu'] for s in dxvk['samples']]
    dxvk_rss = [s['rss_mb'] for s in dxvk['samples']]

    wined3d_times = [s['time'] for s in wined3d['samples']]
    wined3d_cpu = [s['cpu'] for s in wined3d['samples']]
    wined3d_rss = [s['rss_mb'] for s in wined3d['samples']]

    # Filter to "active" gameplay (CPU > 50%) for fair comparison
    dxvk_active_cpu = [c for c in dxvk_cpu if c > 50]
    wined3d_active_cpu = [c for c in wined3d_cpu if c > 50]

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('DXVK vs WineD3D Performance Comparison\nFallout New Vegas on macOS (M4 Pro)',
                 fontsize=14, fontweight='bold')

    # Color scheme
    dxvk_color = '#2ecc71'  # Green
    wined3d_color = '#e74c3c'  # Red

    # Plot 1: CPU Usage over time
    ax1 = axes[0, 0]
    ax1.plot(dxvk_times, dxvk_cpu, label='DXVK', color=dxvk_color, linewidth=1.5)
    ax1.plot(wined3d_times, wined3d_cpu, label='WineD3D', color=wined3d_color, linewidth=1.5, alpha=0.8)
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('CPU Usage (%)')
    ax1.set_title('CPU Usage Over Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.5, label='1 core')
    ax1.axhline(y=200, color='gray', linestyle='--', alpha=0.3)

    # Plot 2: Memory Usage over time
    ax2 = axes[0, 1]
    ax2.plot(dxvk_times, dxvk_rss, label='DXVK', color=dxvk_color, linewidth=1.5)
    ax2.plot(wined3d_times, wined3d_rss, label='WineD3D', color=wined3d_color, linewidth=1.5, alpha=0.8)
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Memory RSS (MB)')
    ax2.set_title('Memory Usage Over Time')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: CPU Distribution (box plot)
    ax3 = axes[1, 0]
    bp = ax3.boxplot([dxvk_active_cpu, wined3d_active_cpu],
                      labels=['DXVK', 'WineD3D'],
                      patch_artist=True)
    bp['boxes'][0].set_facecolor(dxvk_color)
    bp['boxes'][1].set_facecolor(wined3d_color)
    ax3.set_ylabel('CPU Usage (%)')
    ax3.set_title('CPU Distribution (Active Gameplay, >50%)')
    ax3.grid(True, alpha=0.3, axis='y')

    # Add mean markers
    means = [np.mean(dxvk_active_cpu), np.mean(wined3d_active_cpu)]
    ax3.scatter([1, 2], means, color='black', marker='D', s=50, zorder=3, label='Mean')
    for i, m in enumerate(means):
        ax3.annotate(f'{m:.1f}%', (i+1, m), textcoords="offset points",
                    xytext=(10, 0), fontsize=9)

    # Plot 4: Summary stats bar chart
    ax4 = axes[1, 1]
    categories = ['CPU Avg\n(Active)', 'CPU Max', 'Memory Avg\n(MB/10)']
    dxvk_vals = [np.mean(dxvk_active_cpu), max(dxvk_cpu), np.mean(dxvk_rss)/10]
    wined3d_vals = [np.mean(wined3d_active_cpu), max(wined3d_cpu), np.mean(wined3d_rss)/10]

    x = np.arange(len(categories))
    width = 0.35

    bars1 = ax4.bar(x - width/2, dxvk_vals, width, label='DXVK', color=dxvk_color)
    bars2 = ax4.bar(x + width/2, wined3d_vals, width, label='WineD3D', color=wined3d_color)

    ax4.set_ylabel('Value')
    ax4.set_title('Summary Comparison')
    ax4.set_xticks(x)
    ax4.set_xticklabels(categories)
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        ax4.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8)
    for bar in bars2:
        height = bar.get_height()
        ax4.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8)

    plt.tight_layout()

    # Save figure
    output_path = os.path.join(output_dir, 'benchmark_comparison.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Graph saved to: {output_path}")

    # Print detailed analysis
    print("\n" + "="*70)
    print("DETAILED ANALYSIS: DXVK vs WineD3D")
    print("="*70)

    print("\n## CPU Usage (Active Gameplay Only, >50%)")
    print(f"{'Metric':<20} {'DXVK':>12} {'WineD3D':>12} {'Difference':>15}")
    print("-"*60)

    dxvk_cpu_mean = np.mean(dxvk_active_cpu)
    wined3d_cpu_mean = np.mean(wined3d_active_cpu)
    diff = dxvk_cpu_mean - wined3d_cpu_mean
    pct = (diff / wined3d_cpu_mean) * 100
    print(f"{'Average':<20} {dxvk_cpu_mean:>11.1f}% {wined3d_cpu_mean:>11.1f}% {diff:>+10.1f}% ({pct:>+.0f}%)")

    dxvk_cpu_med = np.median(dxvk_active_cpu)
    wined3d_cpu_med = np.median(wined3d_active_cpu)
    diff = dxvk_cpu_med - wined3d_cpu_med
    print(f"{'Median':<20} {dxvk_cpu_med:>11.1f}% {wined3d_cpu_med:>11.1f}% {diff:>+10.1f}%")

    dxvk_cpu_max = max(dxvk_cpu)
    wined3d_cpu_max = max(wined3d_cpu)
    diff = dxvk_cpu_max - wined3d_cpu_max
    print(f"{'Maximum':<20} {dxvk_cpu_max:>11.1f}% {wined3d_cpu_max:>11.1f}% {diff:>+10.1f}%")

    dxvk_cpu_std = np.std(dxvk_active_cpu)
    wined3d_cpu_std = np.std(wined3d_active_cpu)
    diff = dxvk_cpu_std - wined3d_cpu_std
    print(f"{'Std Dev':<20} {dxvk_cpu_std:>11.1f}% {wined3d_cpu_std:>11.1f}% {diff:>+10.1f}%")

    print("\n## Memory Usage (RSS)")
    print(f"{'Metric':<20} {'DXVK':>12} {'WineD3D':>12} {'Difference':>15}")
    print("-"*60)

    dxvk_rss_mean = np.mean(dxvk_rss)
    wined3d_rss_mean = np.mean(wined3d_rss)
    diff = dxvk_rss_mean - wined3d_rss_mean
    pct = (diff / wined3d_rss_mean) * 100
    print(f"{'Average':<20} {dxvk_rss_mean:>10.1f}MB {wined3d_rss_mean:>10.1f}MB {diff:>+9.1f}MB ({pct:>+.0f}%)")

    dxvk_rss_max = max(dxvk_rss)
    wined3d_rss_max = max(wined3d_rss)
    diff = dxvk_rss_max - wined3d_rss_max
    print(f"{'Maximum':<20} {dxvk_rss_max:>10.1f}MB {wined3d_rss_max:>10.1f}MB {diff:>+9.1f}MB")

    print("\n## Key Findings")
    print("-"*60)

    cpu_savings = ((wined3d_cpu_mean - dxvk_cpu_mean) / wined3d_cpu_mean) * 100
    mem_overhead = ((dxvk_rss_mean - wined3d_rss_mean) / wined3d_rss_mean) * 100

    if cpu_savings > 0:
        print(f"* DXVK uses {cpu_savings:.0f}% LESS CPU than WineD3D during active gameplay")
    else:
        print(f"* WineD3D uses {-cpu_savings:.0f}% less CPU than DXVK during active gameplay")

    if mem_overhead > 0:
        print(f"* DXVK uses {mem_overhead:.0f}% MORE memory than WineD3D ({dxvk_rss_mean - wined3d_rss_mean:.0f} MB)")
    else:
        print(f"* DXVK uses {-mem_overhead:.0f}% less memory than WineD3D")

    # CPU variance analysis
    if dxvk_cpu_std < wined3d_cpu_std:
        print(f"* DXVK has MORE STABLE CPU usage (lower variance by {wined3d_cpu_std - dxvk_cpu_std:.1f}%)")
    else:
        print(f"* WineD3D has more stable CPU usage (lower variance by {dxvk_cpu_std - wined3d_cpu_std:.1f}%)")

    print("\n## Interpretation")
    print("-"*60)
    print("""
DXVK (D3D9 -> Vulkan -> MoltenVK -> Metal):
  - Lower CPU usage suggests more efficient GPU offloading
  - Higher memory likely due to Vulkan/Metal descriptor buffers and caches
  - More variable CPU = possible shader compilation or sync overhead

WineD3D (D3D9 -> OpenGL -> macOS OpenGL):
  - Higher CPU suggests more CPU-side rendering work
  - Lower memory footprint (simpler translation layer)
  - Steady CPU = mature, well-optimized path

For gaming: DXVK's lower CPU usage typically means better frame pacing
and more headroom for game logic, despite higher memory usage.
""")

    return output_path


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    logs_dir = os.path.join(project_dir, 'logs')

    dxvk_path = os.path.join(logs_dir, 'bench_dxvk.json')
    wined3d_path = os.path.join(logs_dir, 'bench_wined3d.json')

    if not os.path.exists(dxvk_path) or not os.path.exists(wined3d_path):
        print("Error: Missing benchmark files")
        print(f"  Expected: {dxvk_path}")
        print(f"  Expected: {wined3d_path}")
        sys.exit(1)

    analyze_and_graph(dxvk_path, wined3d_path, logs_dir)
