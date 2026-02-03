#!/usr/bin/env python3
"""Analyze Instruments trace export data for frame timing issues."""

import sys
import xml.etree.ElementTree as ET
import subprocess
import re
from collections import defaultdict

def parse_duration(duration_str):
    """Parse duration string like '101.92 µs' or '16.67 ms' to microseconds."""
    if not duration_str:
        return 0
    match = re.match(r'([\d.]+)\s*(µs|ms|s|ns)', duration_str)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2)
    if unit == 'ns':
        return value / 1000
    elif unit == 'µs':
        return value
    elif unit == 'ms':
        return value * 1000
    elif unit == 's':
        return value * 1000000
    return 0

def analyze_gpu_intervals(trace_path):
    """Analyze GPU intervals from trace."""
    print("Exporting GPU intervals...")
    result = subprocess.run([
        'xctrace', 'export',
        '--input', trace_path,
        '--xpath', '/trace-toc/run[@number="1"]/data/table[@schema="metal-gpu-intervals"]'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return

    # Parse XML
    root = ET.fromstring(result.stdout)

    frame_times = defaultdict(list)  # frame_number -> list of durations
    channel_times = defaultdict(list)  # channel_name -> list of durations

    for row in root.iter('row'):
        duration_elem = row.find('.//duration')
        frame_elem = row.find('.//gpu-frame-number')
        channel_elem = row.find('.//gpu-channel-name')

        if duration_elem is not None:
            duration_us = parse_duration(duration_elem.get('fmt', ''))

            if frame_elem is not None:
                frame_num = frame_elem.get('fmt', '0')
                frame_times[frame_num].append(duration_us)

            if channel_elem is not None:
                channel = channel_elem.get('fmt', 'unknown')
                channel_times[channel].append(duration_us)

    print(f"\n{'='*60}")
    print("GPU INTERVAL ANALYSIS")
    print(f"{'='*60}")

    # Frame time analysis
    if frame_times:
        frame_totals = [(f, sum(durations)) for f, durations in frame_times.items()]
        frame_totals.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0)

        total_times = [t for _, t in frame_totals]
        if total_times:
            print(f"\nFrames analyzed: {len(total_times)}")
            print(f"Total GPU time per frame:")
            print(f"  Min:  {min(total_times)/1000:.2f} ms")
            print(f"  Max:  {max(total_times)/1000:.2f} ms")
            print(f"  Mean: {sum(total_times)/len(total_times)/1000:.2f} ms")

            # Find slow frames (>33ms = below 30fps)
            slow_frames = [(f, t) for f, t in frame_totals if t > 33000]
            if slow_frames:
                print(f"\n  SLOW FRAMES (>33ms): {len(slow_frames)}")
                for f, t in slow_frames[:10]:
                    print(f"    Frame {f}: {t/1000:.2f} ms")

    # Channel breakdown
    if channel_times:
        print(f"\n{'='*60}")
        print("TIME BY GPU CHANNEL")
        print(f"{'='*60}")

        channel_totals = [(ch, sum(times), len(times)) for ch, times in channel_times.items()]
        channel_totals.sort(key=lambda x: x[1], reverse=True)

        for channel, total, count in channel_totals[:15]:
            avg = total / count if count > 0 else 0
            print(f"  {channel[:40]:40s}: {total/1000:8.2f} ms total, {avg:.1f} µs avg ({count} calls)")

def analyze_driver_intervals(trace_path):
    """Analyze Metal driver (CPU-side) intervals."""
    print("\n" + "="*60)
    print("DRIVER/CPU ENCODING ANALYSIS")
    print("="*60)

    result = subprocess.run([
        'xctrace', 'export',
        '--input', trace_path,
        '--xpath', '/trace-toc/run[@number="1"]/data/table[@schema="metal-driver-intervals"]'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return

    root = ET.fromstring(result.stdout)

    event_times = defaultdict(list)

    for row in root.iter('row'):
        duration_elem = row.find('.//duration')
        event_elem = row.find('.//metal-object-label')

        if duration_elem is not None and event_elem is not None:
            duration_us = parse_duration(duration_elem.get('fmt', ''))
            event_type = event_elem.get('fmt', 'unknown')
            event_times[event_type].append(duration_us)

    if event_times:
        event_totals = [(ev, sum(times), len(times), max(times)) for ev, times in event_times.items()]
        event_totals.sort(key=lambda x: x[1], reverse=True)

        print("\nTop CPU-side Metal operations:")
        for event, total, count, max_time in event_totals[:10]:
            avg = total / count if count > 0 else 0
            print(f"  {event[:35]:35s}: {total/1000:8.2f} ms total, {avg:6.1f} µs avg, {max_time/1000:.2f} ms max ({count}x)")

def analyze_command_buffers(trace_path):
    """Analyze command buffer submissions."""
    print("\n" + "="*60)
    print("COMMAND BUFFER ANALYSIS")
    print("="*60)

    result = subprocess.run([
        'xctrace', 'export',
        '--input', trace_path,
        '--xpath', '/trace-toc/run[@number="1"]/data/table[@schema="metal-application-command-buffer-submissions"]'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        return

    root = ET.fromstring(result.stdout)

    submissions = 0
    for row in root.iter('row'):
        submissions += 1

    print(f"\nTotal command buffer submissions: {submissions}")
    if submissions > 0:
        print(f"Submissions per second: ~{submissions / 10:.1f}")

def main():
    if len(sys.argv) < 2:
        # Find most recent trace
        import glob
        traces = glob.glob('/Users/theo/Coding/moltenvk-fnv-project/logs/traces/*.trace')
        if not traces:
            print("Usage: python analyze_trace.py <trace_file>")
            print("No traces found in logs/traces/")
            sys.exit(1)
        trace_path = max(traces, key=lambda x: x)
        print(f"Using most recent trace: {trace_path}")
    else:
        trace_path = sys.argv[1]

    analyze_gpu_intervals(trace_path)
    analyze_driver_intervals(trace_path)
    analyze_command_buffers(trace_path)

    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    print("""
Open the trace in Instruments for visual analysis:
  open <trace_file>

Look for:
1. GPU Track: Long gaps = CPU bottleneck, solid bars = GPU bottleneck
2. Driver Track: Long encoding times = MoltenVK/SPIRV-Cross overhead
3. Frame boundaries: Irregular spacing = frame pacing issues
""")

if __name__ == '__main__':
    main()
