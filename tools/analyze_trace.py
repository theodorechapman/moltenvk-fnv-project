#!/usr/bin/env python3
"""Analyze Instruments trace export data for frame timing issues.

Also supports real-time performance monitoring of FNV for comparing DXVK vs WineD3D.

Usage:
    python analyze_trace.py                    # Analyze most recent trace
    python analyze_trace.py <trace_file>       # Analyze specific trace
    python analyze_trace.py --monitor          # Real-time perf monitoring
    python analyze_trace.py --monitor --duration 60  # Monitor for 60 seconds
    python analyze_trace.py --frames           # Real-time frame time capture
    python analyze_trace.py --parse-log <log>  # Parse DXVK/MVK log for timing
"""

import sys
import xml.etree.ElementTree as ET
import subprocess
import re
import time
import argparse
import json
import os
import signal
import threading
from collections import defaultdict, deque
from datetime import datetime

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

def parse_moltenvk_perf_log(log_path):
    """Parse MoltenVK performance log for timing data.

    Run with MVK_CONFIG_PERFORMANCE_TRACKING=1 and
    MVK_CONFIG_ACTIVITY_PERFORMANCE_LOGGING_STYLE=2 to generate.
    """
    print("=" * 60)
    print("MOLTENVK PERFORMANCE LOG ANALYSIS")
    print("=" * 60)

    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return None

    with open(log_path) as f:
        content = f.read()

    # Parse MVK performance stats
    # Example: "[mvk-perf] VkQueueSubmit ... 1.23 ms"
    perf_pattern = r'\[mvk-perf\]\s+(\w+).*?(\d+\.?\d*)\s*(s|ms|µs)'
    matches = re.findall(perf_pattern, content, re.IGNORECASE)

    stats = defaultdict(list)
    for func, time_val, unit in matches:
        time_us = float(time_val)
        if unit == 'ms':
            time_us *= 1000
        elif unit == 's':
            time_us *= 1000000
        stats[func].append(time_us)

    # Also look for vkWaitSemaphores which is often a bottleneck
    wait_pattern = r'vkWaitSemaphores.*?(\d+\.?\d*)\s*(s|ms|µs)'
    wait_matches = re.findall(wait_pattern, content, re.IGNORECASE)
    for time_val, unit in wait_matches:
        time_us = float(time_val)
        if unit == 'ms':
            time_us *= 1000
        elif unit == 's':
            time_us *= 1000000
        stats['vkWaitSemaphores'].append(time_us)

    # Look for shader compilation
    shader_pattern = r'(compil|SPIRV|MSL).*?(\d+\.?\d*)\s*(s|ms|µs)'
    shader_matches = re.findall(shader_pattern, content, re.IGNORECASE)
    for _, time_val, unit in shader_matches:
        time_us = float(time_val)
        if unit == 'ms':
            time_us *= 1000
        elif unit == 's':
            time_us *= 1000000
        stats['ShaderCompilation'].append(time_us)

    if stats:
        print("\nVulkan Call Timing (from MoltenVK perf log):")
        print(f"{'Function':<30} {'Count':>8} {'Avg':>10} {'Max':>10} {'Total':>12}")
        print("-" * 75)

        sorted_stats = sorted(stats.items(), key=lambda x: sum(x[1]), reverse=True)
        for func, times in sorted_stats[:15]:
            avg = sum(times) / len(times)
            total = sum(times)
            mx = max(times)

            # Format based on magnitude
            def fmt(us):
                if us > 1000000:
                    return f"{us/1000000:.2f}s"
                elif us > 1000:
                    return f"{us/1000:.2f}ms"
                else:
                    return f"{us:.1f}µs"

            print(f"{func:<30} {len(times):>8} {fmt(avg):>10} {fmt(mx):>10} {fmt(total):>12}")

        return stats
    else:
        print("No performance data found in log.")
        print("Make sure to run with:")
        print("  MVK_CONFIG_PERFORMANCE_TRACKING=1")
        print("  MVK_CONFIG_ACTIVITY_PERFORMANCE_LOGGING_STYLE=2")
        return None


def parse_dxvk_log(log_path):
    """Parse DXVK log for shader compilation and present timing."""
    print("\n" + "=" * 60)
    print("DXVK LOG ANALYSIS")
    print("=" * 60)

    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return None

    with open(log_path) as f:
        lines = f.readlines()

    shader_compiles = []
    pipeline_compiles = []
    presents = []
    errors = []
    warnings = []

    for line in lines:
        # Shader compilation
        if 'Compiling shader' in line or 'shader:' in line.lower():
            shader_compiles.append(line.strip())

        # Pipeline compilation
        if 'pipeline' in line.lower() and 'compil' in line.lower():
            pipeline_compiles.append(line.strip())

        # Present/frame timing
        if 'present' in line.lower():
            presents.append(line.strip())

        # Errors
        if 'err:' in line.lower() or 'error' in line.lower():
            errors.append(line.strip())

        # Warnings about unsupported features
        if 'warn:' in line.lower() or 'unsupported' in line.lower() or 'not supported' in line.lower():
            warnings.append(line.strip())

    print(f"\nShader compilations: {len(shader_compiles)}")
    print(f"Pipeline compilations: {len(pipeline_compiles)}")
    print(f"Present calls logged: {len(presents)}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if errors:
        print("\n## Errors (may cause hitches):")
        for e in errors[:10]:
            print(f"  {e[:100]}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    if warnings:
        print("\n## Warnings (may affect performance):")
        seen = set()
        for w in warnings:
            # Deduplicate similar warnings
            key = w[:50]
            if key not in seen:
                print(f"  {w[:120]}")
                seen.add(key)
            if len(seen) >= 10:
                break

    return {
        'shader_compiles': len(shader_compiles),
        'pipeline_compiles': len(pipeline_compiles),
        'errors': errors,
        'warnings': warnings
    }


def capture_frame_times_dtrace(duration=10, output_file=None):
    """Capture frame presentation times using dtrace on Metal/MoltenVK.

    This tracks CAMetalLayer presents to measure actual frame delivery.
    Requires sudo.
    """
    print("=" * 60)
    print("FRAME TIME CAPTURE (requires sudo)")
    print("=" * 60)

    pid = find_fnv_pid()
    if not pid:
        print("\n[ERROR] FalloutNV.exe not running!")
        return None

    print(f"Monitoring PID {pid} for {duration} seconds...")
    print("Note: This requires sudo access for dtrace\n")

    # DTrace script to capture present timing
    dtrace_script = f'''
    syscall::
*
:entry
    /pid == {pid}/
    {{
        self->ts = timestamp;
    }}

    syscall::
*
:return
    /self->ts && pid == {pid}/
    {{
        @calls[probefunc] = count();
        self->ts = 0;
    }}
    '''

    print("Simplified capture - tracking syscall activity...")
    print("For detailed frame times, use: make profile-quick")

    # Instead of dtrace, let's use a simpler approach with sample
    try:
        result = subprocess.run(
            ['sample', str(pid), str(duration), '-f', '/dev/stdout'],
            capture_output=True,
            text=True,
            timeout=duration + 5
        )

        # Parse sample output for hot functions
        output = result.stdout

        # Find the heaviest stack traces
        print("\n## CPU Hot Spots (where time is spent):")

        # Look for function names with high sample counts
        func_pattern = r'(\d+)\s+(\S+)\s+\(in\s+(\S+)\)'
        matches = re.findall(func_pattern, output)

        func_counts = defaultdict(int)
        for count, func, lib in matches:
            if 'libMoltenVK' in lib or 'dxvk' in lib.lower() or 'd3d9' in lib.lower():
                func_counts[f"{func} ({lib})"] += int(count)

        sorted_funcs = sorted(func_counts.items(), key=lambda x: x[1], reverse=True)
        for func, count in sorted_funcs[:15]:
            print(f"  {count:>6}  {func}")

        return sorted_funcs

    except subprocess.TimeoutExpired:
        print("Sample timed out")
        return None
    except Exception as e:
        print(f"Error running sample: {e}")
        return None


def capture_metal_gpu_time(duration=10):
    """Capture Metal GPU execution times using Instruments CLI."""
    print("=" * 60)
    print("METAL GPU TIME CAPTURE")
    print("=" * 60)

    pid = find_fnv_pid()
    if not pid:
        print("\n[ERROR] FalloutNV.exe not running!")
        print("Start the game first.")
        return None

    print(f"Capturing Metal GPU activity for {duration} seconds...")
    print("Move the camera around to capture typical gameplay!\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    trace_dir = os.path.join(project_dir, 'logs', 'traces')
    os.makedirs(trace_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    trace_path = os.path.join(trace_dir, f'diag_{timestamp}.trace')

    try:
        result = subprocess.run([
            'xctrace', 'record',
            '--template', 'Metal System Trace',
            '--attach', str(pid),
            '--time-limit', f'{duration}s',
            '--output', trace_path
        ], capture_output=True, text=True, timeout=duration + 30)

        if result.returncode == 0:
            print(f"\nTrace saved: {trace_path}")
            print("Analyzing...")

            # Auto-analyze the trace
            analyze_gpu_intervals(trace_path)
            analyze_driver_intervals(trace_path)

            return trace_path
        else:
            print(f"xctrace failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print("Trace capture timed out")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def diagnose_hitches(log_dir=None):
    """Comprehensive hitch diagnosis - analyzes all available data."""
    print("=" * 70)
    print("COMPREHENSIVE HITCH DIAGNOSIS")
    print("=" * 70)

    if log_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        log_dir = os.path.join(project_dir, 'logs')

    findings = []

    # 1. Check for DXVK log
    wine_log = os.path.join(log_dir, 'wine.log')
    if os.path.exists(wine_log):
        print("\n## Analyzing DXVK/Wine log...")
        dxvk_data = parse_dxvk_log(wine_log)
        if dxvk_data:
            if dxvk_data['errors']:
                findings.append(f"DXVK has {len(dxvk_data['errors'])} errors - these may cause hitches")
            if dxvk_data['shader_compiles'] > 0:
                findings.append(f"Shader compilation detected ({dxvk_data['shader_compiles']} compiles) - causes stutters on first encounter")

    # 2. Check for MoltenVK perf log
    perf_log = os.path.join(log_dir, 'wine-perf.log')
    if os.path.exists(perf_log):
        print("\n## Analyzing MoltenVK performance log...")
        mvk_data = parse_moltenvk_perf_log(perf_log)
        if mvk_data:
            # Check for slow operations
            for func, times in mvk_data.items():
                max_time = max(times)
                if max_time > 16000:  # > 16ms = dropped frame
                    findings.append(f"{func} has spikes up to {max_time/1000:.1f}ms (causes dropped frames)")

    # 3. Check benchmark data if available
    dxvk_bench = os.path.join(log_dir, 'bench_dxvk.json')
    if os.path.exists(dxvk_bench):
        with open(dxvk_bench) as f:
            bench = json.load(f)

        cpu_samples = [s['cpu'] for s in bench['samples']]
        # Look for CPU spikes
        spikes = [c for c in cpu_samples if c > 200]
        if spikes:
            findings.append(f"CPU spikes detected ({len(spikes)} samples > 200%) - possible sync stalls or compilation")

    # 4. Summary and recommendations
    print("\n" + "=" * 70)
    print("DIAGNOSIS SUMMARY")
    print("=" * 70)

    if findings:
        print("\n## Issues Found:")
        for i, f in enumerate(findings, 1):
            print(f"  {i}. {f}")
    else:
        print("\nNo obvious issues found in logs.")
        print("Run with more diagnostics enabled:")

    print("\n## Recommended Next Steps:")
    print("""
1. CAPTURE DETAILED TIMING DATA:
   make run-perflog    # Run with MoltenVK performance logging

2. THEN ANALYZE:
   uv run python tools/analyze_trace.py --parse-log logs/wine-perf.log

3. CAPTURE GPU TRACE (while game running):
   make profile-quick  # 10-second Metal System Trace

4. FOR REAL-TIME MONITORING:
   # Terminal 1:
   make run-optimized

   # Terminal 2:
   uv run python tools/analyze_trace.py --diagnose

5. COMPARE FRAME PACING:
   Run both renderers in same area and compare:
   - make run-optimized (DXVK)
   - make run-wined3d   (WineD3D)
""")

    print("\n## Common Hitch Causes in DXVK+MoltenVK:")
    print("""
1. SHADER COMPILATION
   - First time seeing an effect = compile stutter
   - Fix: Pre-warm shader cache, or use async compilation

2. vkWaitSemaphores STALLS
   - MoltenVK sync can be slow (seen 20ms+ spikes)
   - Fix: Increase frame latency (d3d9.maxFrameLatency = 3)

3. PIPELINE STATE CHANGES
   - D3D9 changes states frequently, each may trigger recompile
   - Fix: Enable pipeline caching in DXVK

4. DESCRIPTOR SET UPDATES
   - Metal argument buffers have overhead
   - Try: MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=0

5. MEMORY ALLOCATION
   - Dynamic buffer allocation can stall
   - Try: MVK_CONFIG_USE_MTLHEAP=1

6. PRESENT TIMING
   - vsync + triple buffering interaction
   - Try: dxvk.tearFree=False or presentInterval=0
""")

    return findings


def find_fnv_pid():
    """Find the FalloutNV.exe process PID."""
    result = subprocess.run(['pgrep', '-f', 'FalloutNV.exe'], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        return int(result.stdout.strip().split()[0])
    return None


def get_process_stats(pid):
    """Get CPU and memory stats for a process using ps."""
    result = subprocess.run(
        ['ps', '-p', str(pid), '-o', '%cpu,rss,vsz'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().split('\n')
    if len(lines) < 2:
        return None
    parts = lines[1].split()
    if len(parts) < 3:
        return None
    return {
        'cpu_percent': float(parts[0]),
        'rss_mb': int(parts[1]) / 1024,  # RSS in KB -> MB
        'vsz_mb': int(parts[2]) / 1024,  # VSZ in KB -> MB
    }


def detect_renderer():
    """Detect if game is using DXVK or WineD3D based on loaded libraries."""
    pid = find_fnv_pid()
    if not pid:
        return "unknown"

    # Check for DXVK log file or environment
    log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wine_log = os.path.join(log_dir, 'logs', 'wine.log')
    wined3d_log = os.path.join(log_dir, 'logs', 'wine-wined3d.log')

    if os.path.exists(wined3d_log):
        mtime_wined3d = os.path.getmtime(wined3d_log)
        mtime_wine = os.path.getmtime(wine_log) if os.path.exists(wine_log) else 0
        if mtime_wined3d > mtime_wine:
            return "WineD3D"

    return "DXVK"


def monitor_performance(duration_seconds=None, output_file=None):
    """Real-time performance monitoring of FNV."""
    print("=" * 60)
    print("FNV REAL-TIME PERFORMANCE MONITOR")
    print("=" * 60)

    pid = find_fnv_pid()
    if not pid:
        print("\n[ERROR] FalloutNV.exe not running!")
        print("Start the game first with:")
        print("  make run          (DXVK)")
        print("  make run-wined3d  (WineD3D)")
        return

    renderer = detect_renderer()
    print(f"\nMonitoring PID: {pid}")
    print(f"Detected renderer: {renderer}")
    if duration_seconds:
        print(f"Duration: {duration_seconds} seconds")
    print("\nPress Ctrl+C to stop\n")

    # Stats collection
    samples = []
    start_time = time.time()
    sample_interval = 0.5  # Sample every 500ms

    print(f"{'Time':>8s}  {'CPU%':>6s}  {'RSS MB':>8s}  {'Status'}")
    print("-" * 40)

    try:
        while True:
            elapsed = time.time() - start_time

            if duration_seconds and elapsed >= duration_seconds:
                break

            stats = get_process_stats(pid)
            if stats is None:
                print(f"\n[WARN] Process {pid} ended")
                break

            sample = {
                'time': elapsed,
                'cpu': stats['cpu_percent'],
                'rss_mb': stats['rss_mb'],
                'renderer': renderer,
            }
            samples.append(sample)

            # Status indicator based on CPU usage
            status = ""
            if stats['cpu_percent'] > 150:
                status = "🔥 HIGH"
            elif stats['cpu_percent'] < 30:
                status = "⚠️  LOW"

            print(f"{elapsed:7.1f}s  {stats['cpu_percent']:5.1f}%  {stats['rss_mb']:7.1f}  {status}")

            time.sleep(sample_interval)

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    # Summary
    if samples:
        print("\n" + "=" * 60)
        print(f"PERFORMANCE SUMMARY ({renderer})")
        print("=" * 60)

        cpu_values = [s['cpu'] for s in samples]
        rss_values = [s['rss_mb'] for s in samples]

        print(f"\nCPU Usage:")
        print(f"  Min:  {min(cpu_values):6.1f}%")
        print(f"  Max:  {max(cpu_values):6.1f}%")
        print(f"  Avg:  {sum(cpu_values)/len(cpu_values):6.1f}%")

        print(f"\nMemory (RSS):")
        print(f"  Min:  {min(rss_values):6.1f} MB")
        print(f"  Max:  {max(rss_values):6.1f} MB")
        print(f"  Avg:  {sum(rss_values)/len(rss_values):6.1f} MB")

        print(f"\nSamples: {len(samples)} over {samples[-1]['time']:.1f}s")

        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                json.dump({
                    'renderer': renderer,
                    'timestamp': datetime.now().isoformat(),
                    'samples': samples,
                    'summary': {
                        'cpu_min': min(cpu_values),
                        'cpu_max': max(cpu_values),
                        'cpu_avg': sum(cpu_values)/len(cpu_values),
                        'rss_min': min(rss_values),
                        'rss_max': max(rss_values),
                        'rss_avg': sum(rss_values)/len(rss_values),
                    }
                }, f, indent=2)
            print(f"\nResults saved to: {output_file}")


def compare_results(dxvk_file, wined3d_file):
    """Compare two performance result files."""
    with open(dxvk_file) as f:
        dxvk = json.load(f)
    with open(wined3d_file) as f:
        wined3d = json.load(f)

    print("=" * 60)
    print("DXVK vs WineD3D COMPARISON")
    print("=" * 60)

    print(f"\n{'Metric':<20s}  {'DXVK':>12s}  {'WineD3D':>12s}  {'Diff':>12s}")
    print("-" * 60)

    metrics = [
        ('CPU Avg %', 'cpu_avg'),
        ('CPU Max %', 'cpu_max'),
        ('RSS Avg MB', 'rss_avg'),
        ('RSS Max MB', 'rss_max'),
    ]

    for label, key in metrics:
        d_val = dxvk['summary'][key]
        w_val = wined3d['summary'][key]
        diff = d_val - w_val
        diff_str = f"{diff:+.1f}"
        print(f"{label:<20s}  {d_val:>12.1f}  {w_val:>12.1f}  {diff_str:>12s}")

    print("\n(Negative diff = DXVK uses less)")


def main():
    parser = argparse.ArgumentParser(description='Analyze FNV performance')
    parser.add_argument('trace_file', nargs='?', help='Trace file to analyze')
    parser.add_argument('--monitor', '-m', action='store_true',
                        help='Real-time performance monitoring')
    parser.add_argument('--duration', '-d', type=int, default=30,
                        help='Monitoring duration in seconds (default: 30)')
    parser.add_argument('--output', '-o', type=str,
                        help='Save monitoring results to JSON file')
    parser.add_argument('--compare', '-c', nargs=2, metavar=('DXVK', 'WINED3D'),
                        help='Compare two result JSON files')
    parser.add_argument('--parse-log', '-p', type=str,
                        help='Parse DXVK/MoltenVK log file for timing data')
    parser.add_argument('--diagnose', action='store_true',
                        help='Run comprehensive hitch diagnosis')
    parser.add_argument('--capture-gpu', action='store_true',
                        help='Capture Metal GPU trace (requires running game)')
    parser.add_argument('--sample-cpu', action='store_true',
                        help='Sample CPU activity in game process')

    args = parser.parse_args()

    if args.compare:
        compare_results(args.compare[0], args.compare[1])
        return

    if args.diagnose:
        diagnose_hitches()
        return

    if args.parse_log:
        # Determine log type and parse accordingly
        log_path = args.parse_log
        if 'perf' in log_path.lower():
            parse_moltenvk_perf_log(log_path)
        parse_dxvk_log(log_path)
        return

    if args.capture_gpu:
        capture_metal_gpu_time(args.duration)
        return

    if args.sample_cpu:
        capture_frame_times_dtrace(args.duration)
        return

    if args.monitor:
        monitor_performance(args.duration, args.output)
        return

    # Original trace analysis
    if args.trace_file is None:
        # Find most recent trace
        import glob
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        traces = glob.glob(os.path.join(project_dir, 'logs/traces/*.trace'))
        if not traces:
            print("Usage: python analyze_trace.py <trace_file>")
            print("       python analyze_trace.py --monitor")
            print("\nNo traces found in logs/traces/")
            sys.exit(1)
        trace_path = max(traces, key=os.path.getmtime)
        print(f"Using most recent trace: {trace_path}")
    else:
        trace_path = args.trace_file

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
