#!/usr/bin/env python3
"""Parse MoltenVK API trace log to find slow Vulkan calls.

Run the game with:
  make run-apitrace

Then analyze with:
  uv run python tools/parse_apitrace.py logs/wine-apitrace.log
"""

import sys
import re
from collections import defaultdict
import os

def parse_apitrace(log_path):
    """Parse MVK API trace for timing data."""

    if not os.path.exists(log_path):
        print(f"Error: {log_path} not found")
        print("Run: make run-apitrace first")
        sys.exit(1)

    print("=" * 70)
    print("MOLTENVK API TRACE ANALYSIS")
    print("=" * 70)
    print(f"Parsing: {log_path}")

    # MVK trace format varies, common patterns:
    # [mvk-trace] vkFunctionName() ... time
    # or just: vkFunctionName ...duration...

    call_times = defaultdict(list)
    call_counts = defaultdict(int)
    slow_calls = []  # (function, time_ms, line_num)

    # Patterns to match
    patterns = [
        # Pattern 1: [mvk-trace] vkFunc() ... 123.45 µs
        r'\[mvk-trace\]\s+(vk\w+)\([^)]*\).*?(\d+\.?\d*)\s*(ns|µs|us|ms|s)\b',
        # Pattern 2: vkFunc ... 123.45 µs
        r'(vk\w+).*?(\d+\.?\d*)\s*(ns|µs|us|ms|s)\b',
        # Pattern 3: MVK activity: vkFunc 123.45 µs
        r'(vk\w+)\s+(\d+\.?\d*)\s*(ns|µs|us|ms|s)',
    ]

    with open(log_path, 'r', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            # Skip non-vulkan lines
            if 'vk' not in line.lower():
                continue

            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    func = match.group(1)
                    time_val = float(match.group(2))
                    unit = match.group(3).lower()

                    # Normalize to microseconds
                    if unit == 'ns':
                        time_us = time_val / 1000
                    elif unit in ('µs', 'us'):
                        time_us = time_val
                    elif unit == 'ms':
                        time_us = time_val * 1000
                    elif unit == 's':
                        time_us = time_val * 1000000
                    else:
                        time_us = time_val

                    call_times[func].append(time_us)
                    call_counts[func] += 1

                    # Track slow calls (>1ms)
                    if time_us > 1000:
                        slow_calls.append((func, time_us / 1000, line_num))

                    break  # Use first matching pattern

    if not call_times:
        print("\nNo timing data found in trace.")
        print("Make sure MVK_CONFIG_TRACE_VULKAN_CALLS=3 is set.")
        print("\nSearching for any vk* mentions...")

        with open(log_path, 'r', errors='ignore') as f:
            vk_lines = [l for l in f if 'vk' in l.lower()][:20]

        if vk_lines:
            print("Found vk references (first 20):")
            for l in vk_lines:
                print(f"  {l.strip()[:100]}")
        return

    # Summary by function
    print(f"\nTotal unique Vulkan functions called: {len(call_times)}")
    print(f"Total Vulkan calls: {sum(call_counts.values())}")

    print("\n" + "=" * 70)
    print("VULKAN CALL TIMING SUMMARY")
    print("=" * 70)
    print(f"{'Function':<40} {'Count':>8} {'Avg':>10} {'Max':>10} {'Total':>12}")
    print("-" * 85)

    # Sort by total time
    sorted_funcs = sorted(
        call_times.items(),
        key=lambda x: sum(x[1]),
        reverse=True
    )

    def fmt_time(us):
        if us > 1000000:
            return f"{us/1000000:.2f}s"
        elif us > 1000:
            return f"{us/1000:.2f}ms"
        else:
            return f"{us:.1f}µs"

    for func, times in sorted_funcs[:25]:
        avg = sum(times) / len(times)
        mx = max(times)
        total = sum(times)
        print(f"{func:<40} {len(times):>8} {fmt_time(avg):>10} {fmt_time(mx):>10} {fmt_time(total):>12}")

    # Slow call analysis
    if slow_calls:
        print("\n" + "=" * 70)
        print(f"SLOW CALLS (>1ms) - {len(slow_calls)} total")
        print("=" * 70)

        # Group by function
        slow_by_func = defaultdict(list)
        for func, time_ms, line in slow_calls:
            slow_by_func[func].append(time_ms)

        sorted_slow = sorted(slow_by_func.items(), key=lambda x: max(x[1]), reverse=True)

        print(f"{'Function':<40} {'Count':>8} {'Max ms':>10} {'Avg ms':>10}")
        print("-" * 70)
        for func, times in sorted_slow[:15]:
            print(f"{func:<40} {len(times):>8} {max(times):>10.2f} {sum(times)/len(times):>10.2f}")

    # Frame-dropping analysis
    print("\n" + "=" * 70)
    print("FRAME DROP ANALYSIS")
    print("=" * 70)

    # Calls that could cause frame drops (>16ms)
    frame_droppers = [(f, t, l) for f, t, l in slow_calls if t > 16]
    if frame_droppers:
        print(f"\nCalls causing frame drops (>16ms): {len(frame_droppers)}")

        dropper_funcs = defaultdict(list)
        for func, time_ms, line in frame_droppers:
            dropper_funcs[func].append(time_ms)

        for func, times in sorted(dropper_funcs.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  {func}: {len(times)}x (max {max(times):.1f}ms)")
    else:
        print("No individual calls >16ms found.")

    # Identify likely bottlenecks
    print("\n" + "=" * 70)
    print("LIKELY BOTTLENECKS")
    print("=" * 70)

    bottlenecks = []

    # Check for common problematic functions
    problem_funcs = {
        'vkWaitSemaphores': 'GPU/CPU sync - increase frame latency',
        'vkQueueSubmit': 'Command buffer submission - batch more work',
        'vkCreateGraphicsPipelines': 'Pipeline compilation - enable caching',
        'vkCreateShaderModule': 'Shader compilation - use pipeline cache',
        'vkAllocateDescriptorSets': 'Descriptor allocation - use pools',
        'vkAllocateMemory': 'Memory allocation - use MTLHeap',
        'vkMapMemory': 'Memory mapping - reduce frequency',
        'vkQueuePresentKHR': 'Present - check vsync settings',
        'vkAcquireNextImageKHR': 'Swapchain acquire - check frame latency',
        'vkWaitForFences': 'Fence wait - GPU falling behind',
        'vkDeviceWaitIdle': 'Full GPU sync - avoid if possible',
    }

    for func, advice in problem_funcs.items():
        if func in call_times:
            times = call_times[func]
            avg = sum(times) / len(times)
            mx = max(times)

            # Flag if slow
            if mx > 5000 or (avg > 1000 and len(times) > 10):
                bottlenecks.append((func, avg, mx, len(times), advice))

    if bottlenecks:
        for func, avg, mx, count, advice in sorted(bottlenecks, key=lambda x: x[2], reverse=True):
            print(f"\n  {func}")
            print(f"    Calls: {count}, Avg: {fmt_time(avg)}, Max: {fmt_time(mx)}")
            print(f"    Fix: {advice}")
    else:
        print("No obvious bottlenecks detected in common functions.")

    return call_times


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Default to wine-apitrace.log
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        log_path = os.path.join(project_dir, 'logs', 'wine-apitrace.log')
    else:
        log_path = sys.argv[1]

    parse_apitrace(log_path)
