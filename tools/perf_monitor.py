#!/usr/bin/env python3
"""
DXVK Performance Monitor

Reads performance data from DXVK's shared memory and displays
real-time graphs and statistics. Also logs to CSV for analysis.

Usage: python3 perf_monitor.py [--log output.csv]
"""

import argparse
import csv
import ctypes
import mmap
import os
import struct
import sys
import time
from collections import deque
from datetime import datetime

# Check for required packages
try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("Error: tkinter not available. Install with: brew install python-tk")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.animation as animation
except ImportError:
    print("Error: matplotlib not available. Install with: pip3 install matplotlib")
    sys.exit(1)


# Shared memory structure (must match dxvk_perf_monitor.h)
MAGIC = 0x44585646  # "DXVF"
VERSION = 1
HISTORY_SIZE = 300

# The file is created at C:\dxvk_perf.dat in Wine, which maps to the prefix's drive_c
# We'll search common locations
PERF_FILE_LOCATIONS = [
    # Relative to script location (assuming run from project root)
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "wine-prefix-11", "drive_c", "dxvk_perf.dat"),
    # Absolute fallback
    "/Users/theo/Coding/moltenvk-fnv-project/wine-prefix-11/drive_c/dxvk_perf.dat",
    # Legacy location
    "/tmp/dxvk_perf.dat",
]


class DxvkPerfData(ctypes.Structure):
    """Mirror of the C++ DxvkPerfData structure"""
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("version", ctypes.c_uint32),

        # Frame timing (microseconds)
        ("frameTimeUs", ctypes.c_uint64),
        ("frameTimeMinUs", ctypes.c_uint64),
        ("frameTimeMaxUs", ctypes.c_uint64),
        ("frameTimeAvgUs", ctypes.c_uint64),

        # Frame counter
        ("frameCount", ctypes.c_uint64),
        ("timestamp", ctypes.c_uint64),

        # FPS
        ("fps", ctypes.c_float),
        ("fpsAvg", ctypes.c_float),

        # Draw statistics
        ("drawCalls", ctypes.c_uint32),
        ("drawCallsIndexed", ctypes.c_uint32),
        ("drawCallsInstanced", ctypes.c_uint32),
        ("primitiveCount", ctypes.c_uint32),

        # Pipeline statistics
        ("renderPasses", ctypes.c_uint32),
        ("computeDispatches", ctypes.c_uint32),
        ("submissions", ctypes.c_uint32),

        # Resource statistics
        ("textureBinds", ctypes.c_uint32),
        ("bufferBinds", ctypes.c_uint32),
        ("shaderBinds", ctypes.c_uint32),
        ("pipelineBinds", ctypes.c_uint32),

        # Memory (bytes)
        ("gpuMemoryUsed", ctypes.c_uint64),
        ("gpuMemoryBudget", ctypes.c_uint64),
        ("gpuMemoryAllocated", ctypes.c_uint64),

        # Shader compilation
        ("shadersCompiled", ctypes.c_uint32),
        ("shadersTotal", ctypes.c_uint32),
        ("pipelinesCompiled", ctypes.c_uint32),
        ("pipelinesTotal", ctypes.c_uint32),

        # Swapchain info
        ("swapchainWidth", ctypes.c_uint32),
        ("swapchainHeight", ctypes.c_uint32),
        ("presentMode", ctypes.c_uint32),
        ("backBufferCount", ctypes.c_uint32),

        # Sync statistics
        ("gpuIdleTimeUs", ctypes.c_uint64),
        ("cpuWaitTimeUs", ctypes.c_uint64),

        # Frame time history
        ("historyIndex", ctypes.c_uint32),
        ("historyFrameTimes", ctypes.c_uint32 * HISTORY_SIZE),

        # Reserved
        ("reserved", ctypes.c_uint8 * 256),
    ]


class SharedMemoryReader:
    """Reads DXVK performance data from memory-mapped file"""

    def __init__(self):
        self.fd = None
        self.mm = None
        self.connected = False
        self.perf_file = None

    def connect(self):
        """Try to connect to the performance data file"""
        # Try each possible location
        for perf_file in PERF_FILE_LOCATIONS:
            try:
                if not os.path.exists(perf_file):
                    continue

                self.fd = os.open(perf_file, os.O_RDONLY)
                file_size = os.fstat(self.fd).st_size

                if file_size < ctypes.sizeof(DxvkPerfData):
                    os.close(self.fd)
                    self.fd = None
                    continue

                self.mm = mmap.mmap(self.fd, ctypes.sizeof(DxvkPerfData), access=mmap.ACCESS_READ)
                self.perf_file = perf_file
                self.connected = True
                print(f"Connected to: {perf_file}")
                return True

            except (FileNotFoundError, OSError, PermissionError):
                if self.fd is not None:
                    os.close(self.fd)
                    self.fd = None
                continue
            except Exception as e:
                print(f"Connection error: {e}")
                continue

        return False

    def read(self):
        """Read current performance data"""
        if not self.connected or self.mm is None:
            return None

        try:
            self.mm.seek(0)
            data = DxvkPerfData.from_buffer_copy(self.mm.read(ctypes.sizeof(DxvkPerfData)))

            # Validate magic number
            if data.magic != MAGIC:
                return None

            return data
        except Exception as e:
            print(f"Read error: {e}")
            self.connected = False
            return None

    def close(self):
        """Close the memory-mapped file"""
        if self.mm:
            self.mm.close()
            self.mm = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.connected = False


class PerfMonitorApp:
    """Main application window"""

    def __init__(self, log_file=None):
        self.root = tk.Tk()
        self.root.title("DXVK Performance Monitor")
        self.root.geometry("1000x700")
        self.root.configure(bg='#1e1e1e')

        self.reader = SharedMemoryReader()
        self.log_file = log_file
        self.csv_writer = None
        self.csv_file = None

        if log_file:
            self.csv_file = open(log_file, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                'timestamp', 'frame_time_us', 'fps', 'fps_avg',
                'draw_calls', 'primitives', 'submissions',
                'shaders_compiled', 'pipelines_compiled',
                'gpu_memory_mb'
            ])

        # Data history for graphs
        self.frame_times = deque(maxlen=HISTORY_SIZE)
        self.fps_history = deque(maxlen=HISTORY_SIZE)
        self.draw_calls_history = deque(maxlen=HISTORY_SIZE)

        self.setup_ui()
        self.last_frame_count = 0

        # Start update loop
        self.update()

    def setup_ui(self):
        """Create the UI"""
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#1e1e1e', foreground='#ffffff', font=('Menlo', 11))
        style.configure('TFrame', background='#1e1e1e')
        style.configure('Header.TLabel', font=('Menlo', 14, 'bold'), foreground='#61afef')
        style.configure('Value.TLabel', font=('Menlo', 24, 'bold'), foreground='#98c379')
        style.configure('Status.TLabel', font=('Menlo', 10), foreground='#e06c75')

        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top row - connection status and main stats
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(top_frame, text="Waiting for DXVK...", style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)

        # Stats row
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=10)

        # FPS
        fps_frame = ttk.Frame(stats_frame)
        fps_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(fps_frame, text="FPS", style='Header.TLabel').pack()
        self.fps_label = ttk.Label(fps_frame, text="--", style='Value.TLabel')
        self.fps_label.pack()
        self.fps_avg_label = ttk.Label(fps_frame, text="avg: --")
        self.fps_avg_label.pack()

        # Frame Time
        ft_frame = ttk.Frame(stats_frame)
        ft_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(ft_frame, text="Frame Time", style='Header.TLabel').pack()
        self.ft_label = ttk.Label(ft_frame, text="-- ms", style='Value.TLabel')
        self.ft_label.pack()
        self.ft_minmax_label = ttk.Label(ft_frame, text="min/max: --/--")
        self.ft_minmax_label.pack()

        # Draw Calls
        dc_frame = ttk.Frame(stats_frame)
        dc_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(dc_frame, text="Draw Calls", style='Header.TLabel').pack()
        self.dc_label = ttk.Label(dc_frame, text="--", style='Value.TLabel')
        self.dc_label.pack()
        self.dc_detail_label = ttk.Label(dc_frame, text="idx: -- inst: --")
        self.dc_detail_label.pack()

        # Submissions
        sub_frame = ttk.Frame(stats_frame)
        sub_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(sub_frame, text="Submissions", style='Header.TLabel').pack()
        self.sub_label = ttk.Label(sub_frame, text="--", style='Value.TLabel')
        self.sub_label.pack()

        # Shaders
        shader_frame = ttk.Frame(stats_frame)
        shader_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(shader_frame, text="Shaders", style='Header.TLabel').pack()
        self.shader_label = ttk.Label(shader_frame, text="--", style='Value.TLabel')
        self.shader_label.pack()
        self.shader_detail_label = ttk.Label(shader_frame, text="compiled: --")
        self.shader_detail_label.pack()

        # Graph area
        graph_frame = ttk.Frame(main_frame)
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Create matplotlib figure
        self.fig = Figure(figsize=(10, 4), dpi=100, facecolor='#1e1e1e')

        # Frame time graph
        self.ax1 = self.fig.add_subplot(121)
        self.ax1.set_facecolor('#2d2d2d')
        self.ax1.set_title('Frame Time (ms)', color='white', fontsize=10)
        self.ax1.tick_params(colors='white')
        self.ax1.set_ylim(0, 50)
        self.line1, = self.ax1.plot([], [], color='#61afef', linewidth=1)
        self.ax1.axhline(y=16.67, color='#98c379', linestyle='--', alpha=0.5, label='60 FPS')
        self.ax1.axhline(y=33.33, color='#e5c07b', linestyle='--', alpha=0.5, label='30 FPS')
        self.ax1.legend(loc='upper right', fontsize=8, facecolor='#2d2d2d', edgecolor='#3d3d3d', labelcolor='white')

        # Draw calls graph
        self.ax2 = self.fig.add_subplot(122)
        self.ax2.set_facecolor('#2d2d2d')
        self.ax2.set_title('Draw Calls / Frame', color='white', fontsize=10)
        self.ax2.tick_params(colors='white')
        self.line2, = self.ax2.plot([], [], color='#c678dd', linewidth=1)

        self.fig.tight_layout()

        canvas = FigureCanvasTkAgg(self.fig, graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Bottom info
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=5)

        self.info_label = ttk.Label(bottom_frame, text="Resolution: -- | Present Mode: -- | Memory: --")
        self.info_label.pack(side=tk.LEFT)

        self.frame_count_label = ttk.Label(bottom_frame, text="Frames: --")
        self.frame_count_label.pack(side=tk.RIGHT)

    def update(self):
        """Update loop"""
        if not self.reader.connected:
            if self.reader.connect():
                self.status_label.config(text="Connected to DXVK", foreground='#98c379')
            else:
                self.status_label.config(text="Waiting for DXVK... (start game first)", foreground='#e06c75')
                self.root.after(500, self.update)
                return

        data = self.reader.read()

        if data is None:
            self.status_label.config(text="Connection lost, reconnecting...", foreground='#e5c07b')
            self.reader.connected = False
            self.root.after(500, self.update)
            return

        # Check if we have new data
        if data.frameCount == self.last_frame_count:
            self.root.after(16, self.update)  # ~60fps update rate
            return

        self.last_frame_count = data.frameCount

        # Update stats
        frame_time_ms = data.frameTimeUs / 1000.0
        self.fps_label.config(text=f"{data.fps:.1f}")
        self.fps_avg_label.config(text=f"avg: {data.fpsAvg:.1f}")

        self.ft_label.config(text=f"{frame_time_ms:.2f} ms")
        self.ft_minmax_label.config(
            text=f"min/max: {data.frameTimeMinUs/1000:.1f}/{data.frameTimeMaxUs/1000:.1f}"
        )

        self.dc_label.config(text=str(data.drawCalls))
        self.dc_detail_label.config(
            text=f"idx: {data.drawCallsIndexed} inst: {data.drawCallsInstanced}"
        )

        self.sub_label.config(text=str(data.submissions))

        self.shader_label.config(text=str(data.shadersTotal))
        self.shader_detail_label.config(
            text=f"compiled: {data.shadersCompiled} pipes: {data.pipelinesCompiled}"
        )

        # Present mode names
        present_modes = {
            0: "IMMEDIATE",
            1: "MAILBOX",
            2: "FIFO",
            3: "FIFO_RELAXED"
        }
        present_mode = present_modes.get(data.presentMode, f"Unknown({data.presentMode})")

        gpu_mem_mb = data.gpuMemoryUsed / (1024 * 1024)
        self.info_label.config(
            text=f"Resolution: {data.swapchainWidth}x{data.swapchainHeight} | "
                 f"Present: {present_mode} | Memory: {gpu_mem_mb:.0f} MB"
        )

        self.frame_count_label.config(text=f"Frames: {data.frameCount:,}")

        # Update graphs
        self.frame_times.append(frame_time_ms)
        self.draw_calls_history.append(data.drawCalls)

        x_data = list(range(len(self.frame_times)))

        self.line1.set_data(x_data, list(self.frame_times))
        self.ax1.set_xlim(0, max(HISTORY_SIZE, len(self.frame_times)))
        max_ft = max(self.frame_times) if self.frame_times else 50
        self.ax1.set_ylim(0, max(50, max_ft * 1.2))

        self.line2.set_data(x_data, list(self.draw_calls_history))
        self.ax2.set_xlim(0, max(HISTORY_SIZE, len(self.draw_calls_history)))
        max_dc = max(self.draw_calls_history) if self.draw_calls_history else 100
        self.ax2.set_ylim(0, max(100, max_dc * 1.2))

        self.fig.canvas.draw_idle()

        # Log to CSV
        if self.csv_writer:
            self.csv_writer.writerow([
                datetime.now().isoformat(),
                data.frameTimeUs,
                data.fps,
                data.fpsAvg,
                data.drawCalls,
                data.primitiveCount,
                data.submissions,
                data.shadersCompiled,
                data.pipelinesCompiled,
                gpu_mem_mb
            ])

        # Schedule next update
        self.root.after(16, self.update)

    def run(self):
        """Run the application"""
        try:
            self.root.mainloop()
        finally:
            self.reader.close()
            if self.csv_file:
                self.csv_file.close()


def main():
    parser = argparse.ArgumentParser(description='DXVK Performance Monitor')
    parser.add_argument('--log', '-l', help='Log performance data to CSV file')
    args = parser.parse_args()

    print("DXVK Performance Monitor")
    print("=" * 40)
    print("Looking for performance data in:")
    for loc in PERF_FILE_LOCATIONS:
        print(f"  - {loc}")
    print()
    print("Start the game with 'make run' in another terminal")
    print()

    app = PerfMonitorApp(log_file=args.log)
    app.run()


if __name__ == '__main__':
    main()
