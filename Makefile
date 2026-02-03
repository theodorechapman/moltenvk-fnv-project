# MoltenVK FNV Development Makefile
# Usage: make <target>

PROJECT_ROOT := $(shell pwd)
MOLTENVK_DIR := $(PROJECT_ROOT)/MoltenVK
DXVK_DIR := $(PROJECT_ROOT)/DXVK
WINEPREFIX := $(PROJECT_ROOT)/wine-prefix-11
FNV_DIR := $(WINEPREFIX)/drive_c/Games/Steam/steamapps/common/Fallout New Vegas
MO2_DIR := $(WINEPREFIX)/drive_c/MO2
LOGS_DIR := $(PROJECT_ROOT)/logs
BUILD_DIR := $(PROJECT_ROOT)/build

# Wine 11 prefix for development
WINE11_PREFIX := $(PROJECT_ROOT)/wine-prefix-11

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

.PHONY: all build-mvk build-dxvk dxvk run test run-fnv clean logs help clear

# ============================================
# Main targets
# ============================================

all: build-mvk build-dxvk
	@echo "$(GREEN)Build complete$(NC)"

help:
	@echo "MoltenVK FNV Development"
	@echo ""
	@echo "Build targets:"
	@echo "  make build-mvk      - Build MoltenVK"
	@echo "  make build-dxvk     - Build DXVK"
	@echo "  make build-tests    - Build unit tests"
	@echo ""
	@echo "Test targets:"
	@echo "  make test-vulkan    - Verify Vulkan/MoltenVK works"
	@echo "  make test-xfb       - Run transform feedback tests"
	@echo "  make test-gs        - Run geometry shader tests"
	@echo "  make test-unit      - Run all unit tests"
	@echo ""
	@echo "Run targets:"
	@echo "  make run            - Main dev target: rebuild DXVK, clear cache, run"
	@echo "  make run-optimized  - Run with ALL optimizations (MSync, concurrent compile)"
	@echo "  make run-msync      - Run with MSync (native macOS semaphores)"
	@echo "  make run-trace      - Run with full Vulkan call tracing (slow, for analysis)"
	@echo "  make run-perflog    - Run with MoltenVK performance logging"
	@echo "  make run-hud        - Run with DXVK HUD (frametimes graph only)"
	@echo "  make perf-monitor   - Run the performance monitor GUI"
	@echo ""
	@echo "Profiling targets:"
	@echo "  make profile-attach - Attach Metal System Trace to running game (20s)"
	@echo "  make profile-quick  - Quick 10s Metal trace, auto-opens"
	@echo "  make profile-cpu    - CPU Time Profiler trace (15s)"
	@echo "  make profile-open   - Open most recent trace file"
	@echo ""
	@echo "Debug targets:"
	@echo "  make logs           - Tail all log files"
	@echo "  make errors         - Show only errors from logs"
	@echo "  make capture        - Set up Metal frame capture"
	@echo ""
	@echo "Utility targets:"
	@echo "  make install-dxvk   - Install DXVK to Wine prefix"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make clean-logs     - Clean log files"
	@echo "  make clear          - Close all Wine applications and shut down wineserver"

# ============================================
# Build targets
# ============================================

build-mvk:
	@echo "$(YELLOW)Building MoltenVK...$(NC)"
	cd $(MOLTENVK_DIR) && make macos
	@mkdir -p $(BUILD_DIR)/moltenvk
	@cp $(MOLTENVK_DIR)/Package/Latest/MoltenVK/dylib/macOS/libMoltenVK.dylib $(BUILD_DIR)/moltenvk/
	@echo "$(GREEN)MoltenVK built successfully$(NC)"

build-dxvk:
	@echo "$(YELLOW)Building DXVK (32-bit for FNV)...$(NC)"
	cd $(DXVK_DIR) && meson compile -C build.32
	@mkdir -p $(BUILD_DIR)/dxvk
	@cp $(DXVK_DIR)/build.32/src/d3d9/d3d9.dll $(BUILD_DIR)/dxvk/ 2>/dev/null || true
	@cp $(DXVK_DIR)/build.32/src/dxgi/dxgi.dll $(BUILD_DIR)/dxvk/ 2>/dev/null || true
	@echo "$(GREEN)DXVK built$(NC)"

# Quick rebuild DXVK and install to Wine prefix
dxvk: build-dxvk
	@echo "$(YELLOW)Installing DXVK to Wine 11 prefix...$(NC)"
	@cp $(DXVK_DIR)/build.32/src/d3d9/d3d9.dll $(WINE11_PREFIX)/drive_c/windows/syswow64/
	@echo "$(GREEN)DXVK d3d9.dll installed to syswow64$(NC)"

# Main development run target: rebuild DXVK if needed, clear logs/cache, run game
run: dxvk
	@echo "$(YELLOW)Clearing old logs and shader cache...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@rm -f "$(FNV_DIR)"/*.log
	@rm -f "$(FNV_DIR)"/FalloutNV_d3d9.log
	@rm -f "$(FNV_DIR)"/*.dxvk-cache
	@echo "$(YELLOW)Running Fallout NV via NVSE...$(NC)"
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run in Wine virtual desktop (avoids macOS fullscreen issues)
run-vd: dxvk
	@echo "$(YELLOW)Clearing old logs...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@rm -f "$(FNV_DIR)"/*.log
	@echo "$(YELLOW)Running Fallout NV in virtual desktop (1920x1080)...$(NC)"
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	DXVK_LOG_LEVEL=info \
	wine explorer /desktop=FNV,1920x1080 nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

build-tests:
	@echo "$(YELLOW)Building unit tests...$(NC)"
	cd $(PROJECT_ROOT)/tests/unit && make all
	@echo "$(GREEN)Tests built$(NC)"

# ============================================
# Test targets
# ============================================

test-vulkan:
	@echo "$(YELLOW)Testing Vulkan/MoltenVK...$(NC)"
	@vulkaninfo --summary || (echo "$(RED)Vulkan not working$(NC)" && exit 1)
	@echo "$(GREEN)Vulkan OK$(NC)"

test-xfb: build-tests
	@echo "$(YELLOW)Running transform feedback tests...$(NC)"
	@$(BUILD_DIR)/tests/test_xfb 2>&1 | tee $(LOGS_DIR)/test_xfb.log
	@grep -q "PASSED" $(LOGS_DIR)/test_xfb.log && echo "$(GREEN)XFB tests passed$(NC)" || echo "$(RED)XFB tests failed$(NC)"

test-gs: build-tests
	@echo "$(YELLOW)Running geometry shader tests...$(NC)"
	@$(BUILD_DIR)/tests/test_gs 2>&1 | tee $(LOGS_DIR)/test_gs.log
	@grep -q "PASSED" $(LOGS_DIR)/test_gs.log && echo "$(GREEN)GS tests passed$(NC)" || echo "$(RED)GS tests failed$(NC)"

test-unit: test-xfb test-gs
	@echo "$(GREEN)All unit tests complete$(NC)"

# ============================================
# Run targets
# ============================================

run-fnv: install-dxvk
	@echo "$(YELLOW)Running Fallout New Vegas...$(NC)"
	@mkdir -p $(LOGS_DIR)
	@rm -f $(LOGS_DIR)/*.log
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_LOG_LEVEL=2 \
	DXVK_LOG_LEVEL=debug \
	DXVK_LOG_PATH=$(LOGS_DIR) \
	wine64 "$(FNV_DIR)/FalloutNV.exe" 2>&1 | tee $(LOGS_DIR)/wine.log

run-fnv-debug: install-dxvk
	@echo "$(YELLOW)Running FNV with extra debugging...$(NC)"
	@mkdir -p $(LOGS_DIR)
	@rm -f $(LOGS_DIR)/*.log
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_LOG_LEVEL=3 \
	MVK_CONFIG_DEBUG=1 \
	MVK_CONFIG_TRACE_VULKAN_CALLS=1 \
	VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation \
	DXVK_LOG_LEVEL=debug \
	DXVK_LOG_PATH=$(LOGS_DIR) \
	wine64 "$(FNV_DIR)/FalloutNV.exe" 2>&1 | tee $(LOGS_DIR)/wine.log

run-fnv-trace: install-dxvk
	@echo "$(YELLOW)Running FNV with API tracing...$(NC)"
	@mkdir -p $(LOGS_DIR)
	@rm -f $(LOGS_DIR)/*.log
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_LOG_LEVEL=3 \
	MVK_CONFIG_TRACE_VULKAN_CALLS=2 \
	DXVK_LOG_LEVEL=trace \
	DXVK_LOG_PATH=$(LOGS_DIR) \
	wine64 "$(FNV_DIR)/FalloutNV.exe" 2>&1 | tee $(LOGS_DIR)/wine.log

run-fnv-nvse: install-dxvk
	@echo "$(YELLOW)Running FNV with NVSE...$(NC)"
	@mkdir -p $(LOGS_DIR)
	@rm -f $(LOGS_DIR)/*.log
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_LOG_LEVEL=2 \
	DXVK_LOG_LEVEL=debug \
	DXVK_LOG_PATH=$(LOGS_DIR) \
	wine64 "$(FNV_DIR)/nvse_loader.exe" 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with DXVK HUD for performance diagnosis
# NOTE: Only 'frametimes' works - text-based HUD elements (fps, gpuload, etc.)
# use gl_DrawID which MoltenVK doesn't support
run-hud: dxvk
	@echo "$(YELLOW)Running with DXVK HUD (frametimes graph only)...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	DXVK_HUD=frametimes \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

run-fnv-nvse-debug: install-dxvk
	@echo "$(YELLOW)Running FNV with NVSE (debug)...$(NC)"
	@mkdir -p $(LOGS_DIR)
	@rm -f $(LOGS_DIR)/*.log
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_LOG_LEVEL=3 \
	MVK_CONFIG_DEBUG=1 \
	MVK_CONFIG_TRACE_VULKAN_CALLS=1 \
	VK_INSTANCE_LAYERS=VK_LAYER_KHRONOS_validation \
	DXVK_LOG_LEVEL=debug \
	DXVK_LOG_PATH=$(LOGS_DIR) \
	wine64 "$(FNV_DIR)/nvse_loader.exe" 2>&1 | tee $(LOGS_DIR)/wine.log

# Run WITHOUT Metal argument buffers (potential big perf win!)
run-noargbuf: dxvk
	@echo "$(YELLOW)Running WITHOUT Metal Argument Buffers...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=0 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with MoltenVK command buffer prefilling for performance testing
run-prefill: dxvk
	@echo "$(YELLOW)Running with MVK command buffer prefilling...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=1 \
	MVK_CONFIG_PREFILL_METAL_COMMAND_BUFFERS=1 \
	MVK_CONFIG_FAST_MATH_ENABLED=1 \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with higher frame latency (smoother but more input lag)
run-highlatency: dxvk
	@echo "$(YELLOW)Running with HIGH FRAME LATENCY (3 frames)...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	DXVK_LOG_LEVEL=info \
	DXVK_CONFIG_FILE=$(PROJECT_ROOT)/dxvk-highlatency.conf \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with mailbox presentation (no vsync wait, smoother pacing)
run-mailbox: dxvk
	@echo "$(YELLOW)Running with MAILBOX presentation...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	DXVK_LOG_LEVEL=info \
	DXVK_CONFIG_FILE=$(PROJECT_ROOT)/dxvk-mailbox.conf \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with vsync disabled for raw performance testing
run-novsync: dxvk
	@echo "$(YELLOW)Running with VSYNC DISABLED for raw perf test...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	DXVK_LOG_LEVEL=info \
	DXVK_CONFIG_FILE=$(PROJECT_ROOT)/dxvk-novsync.conf \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with MSync (Mach Semaphore) - native macOS synchronization
run-msync: dxvk
	@echo "$(YELLOW)Running with MSYNC (native macOS semaphores)...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	WINEMSYNC=1 \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	MVK_CONFIG_SHOULD_MAXIMIZE_CONCURRENT_COMPILATION=1 \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with full MoltenVK Vulkan call tracing (logs time per call)
run-trace: dxvk
	@echo "$(YELLOW)Running with FULL VULKAN CALL TRACING (slow!)...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	MVK_CONFIG_TRACE_VULKAN_CALLS=5 \
	MVK_CONFIG_PERFORMANCE_TRACKING=1 \
	MVK_CONFIG_ACTIVITY_PERFORMANCE_LOGGING_STYLE=1 \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine-trace.log

# Run with ALL optimizations enabled
run-optimized: dxvk
	@echo "$(YELLOW)Running with ALL OPTIMIZATIONS...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	WINEMSYNC=1 \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	MVK_CONFIG_SHOULD_MAXIMIZE_CONCURRENT_COMPILATION=1 \
	MVK_CONFIG_FAST_MATH_ENABLED=1 \
	MVK_CONFIG_USE_MTLHEAP=1 \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine.log

# Run with performance stats logging (logs every frame)
run-perflog: dxvk
	@echo "$(YELLOW)Running with PERFORMANCE LOGGING...$(NC)"
	@rm -f $(LOGS_DIR)/*.log
	@mkdir -p $(LOGS_DIR)
	cd "$(FNV_DIR)" && \
	WINEPREFIX=$(WINEPREFIX) \
	MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
	MVK_ALLOW_METAL_FENCES=1 \
	MVK_CONFIG_SYNCHRONOUS_QUEUE_SUBMITS=0 \
	MVK_CONFIG_PERFORMANCE_TRACKING=1 \
	MVK_CONFIG_ACTIVITY_PERFORMANCE_LOGGING_STYLE=0 \
	MVK_CONFIG_PERFORMANCE_LOGGING_FRAME_COUNT=60 \
	DXVK_LOG_LEVEL=info \
	wine nvse_loader.exe 2>&1 | tee $(LOGS_DIR)/wine-perf.log

# Run the performance monitor GUI (run in separate terminal, then start game)
perf-monitor:
	@echo "$(YELLOW)Starting DXVK Performance Monitor...$(NC)"
	@echo "Start the game in another terminal with 'make run'"
	python3 $(PROJECT_ROOT)/tools/perf_monitor.py

# Run the performance monitor with logging
perf-monitor-log:
	@echo "$(YELLOW)Starting DXVK Performance Monitor with logging...$(NC)"
	@mkdir -p $(LOGS_DIR)
	python3 $(PROJECT_ROOT)/tools/perf_monitor.py --log $(LOGS_DIR)/perf_$(shell date +%Y%m%d_%H%M%S).csv

# ============================================
# Install/Setup targets
# ============================================

install-dxvk:
	@echo "$(YELLOW)Installing DXVK to Wine prefix...$(NC)"
	@mkdir -p $(WINEPREFIX)/drive_c/windows/syswow64
	@cp $(BUILD_DIR)/dxvk/d3d9.dll $(WINEPREFIX)/drive_c/windows/syswow64/ 2>/dev/null || \
		echo "$(RED)No DXVK DLLs found - run 'make dxvk' first$(NC)"
	@echo "$(GREEN)DXVK installed to syswow64 (32-bit)$(NC)"

install-mvk:
	@echo "$(YELLOW)Installing MoltenVK...$(NC)"
	@sudo cp $(BUILD_DIR)/moltenvk/libMoltenVK.dylib /usr/local/lib/
	@echo "$(GREEN)MoltenVK installed$(NC)"

# ============================================
# Profiling targets (Instruments/Metal System Trace)
# ============================================

# Start game and then run: make profile-attach
# This captures a Metal System Trace for ~20 seconds
profile-attach:
	@echo "$(YELLOW)Looking for Wine/FNV process to attach...$(NC)"
	@PID=$$(pgrep -f "FalloutNV.exe" | head -1); \
	if [ -z "$$PID" ]; then \
		echo "$(RED)No FNV process found. Start the game first with 'make run'$(NC)"; \
		exit 1; \
	fi; \
	echo "$(GREEN)Found process PID: $$PID$(NC)"; \
	echo "$(YELLOW)Recording Metal System Trace for 20 seconds...$(NC)"; \
	echo "$(YELLOW)Move the camera around to capture stutters!$(NC)"; \
	mkdir -p $(LOGS_DIR)/traces; \
	TRACE_FILE=$(LOGS_DIR)/traces/fnv_$$(date +%Y%m%d_%H%M%S).trace; \
	xctrace record --template 'Metal System Trace' \
		--attach $$PID \
		--time-limit 20s \
		--output "$$TRACE_FILE" && \
	echo "$(GREEN)Trace saved to: $$TRACE_FILE$(NC)" && \
	echo "$(GREEN)Open with: open $$TRACE_FILE$(NC)"

# Quick 10-second profile
profile-quick:
	@echo "$(YELLOW)Quick 10s Metal trace...$(NC)"
	@PID=$$(pgrep -f "FalloutNV.exe" | head -1); \
	if [ -z "$$PID" ]; then \
		echo "$(RED)No FNV process found. Start the game first with 'make run'$(NC)"; \
		exit 1; \
	fi; \
	mkdir -p $(LOGS_DIR)/traces; \
	TRACE_FILE=$(LOGS_DIR)/traces/fnv_quick_$$(date +%Y%m%d_%H%M%S).trace; \
	xctrace record --template 'Metal System Trace' \
		--attach $$PID \
		--time-limit 10s \
		--output "$$TRACE_FILE" && \
	echo "$(GREEN)Trace: $$TRACE_FILE$(NC)" && \
	open "$$TRACE_FILE"

# Profile with Time Profiler (CPU analysis)
profile-cpu:
	@echo "$(YELLOW)CPU Time Profile for 15 seconds...$(NC)"
	@PID=$$(pgrep -f "FalloutNV.exe" | head -1); \
	if [ -z "$$PID" ]; then \
		echo "$(RED)No FNV process found. Start the game first with 'make run'$(NC)"; \
		exit 1; \
	fi; \
	mkdir -p $(LOGS_DIR)/traces; \
	TRACE_FILE=$(LOGS_DIR)/traces/fnv_cpu_$$(date +%Y%m%d_%H%M%S).trace; \
	xctrace record --template 'Time Profiler' \
		--attach $$PID \
		--time-limit 15s \
		--output "$$TRACE_FILE" && \
	echo "$(GREEN)CPU trace: $$TRACE_FILE$(NC)" && \
	open "$$TRACE_FILE"

# List available Instruments templates
profile-list:
	@echo "$(YELLOW)Available Instruments templates:$(NC)"
	@xctrace list templates | grep -E "Metal|GPU|Time|System"

# Open most recent trace
profile-open:
	@LATEST=$$(ls -t $(LOGS_DIR)/traces/*.trace 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "$(RED)No traces found in $(LOGS_DIR)/traces/$(NC)"; \
		exit 1; \
	fi; \
	echo "$(GREEN)Opening: $$LATEST$(NC)"; \
	open "$$LATEST"

# ============================================
# Debug/Analysis targets
# ============================================

logs:
	@tail -f $(LOGS_DIR)/*.log

errors:
	@echo "=== MoltenVK Errors ===" 
	@grep -i "error\|fail\|unsupported" $(LOGS_DIR)/*.log 2>/dev/null || echo "No errors found"
	@echo ""
	@echo "=== Missing Extensions ==="
	@grep -i "extension.*not\|not.*support" $(LOGS_DIR)/*.log 2>/dev/null || echo "None found"

capture:
	@echo "Setting up Metal frame capture..."
	@echo "1. Open Xcode"
	@echo "2. Debug > Attach to Process > wine64"
	@echo "3. Debug > Capture GPU Workload"
	@echo ""
	@echo "Or set these environment variables:"
	@echo "  export MTL_CAPTURE_ENABLED=1"
	@echo "  export METAL_CAPTURE_ENABLED=1"

analyze-shaders:
	@echo "$(YELLOW)Analyzing shader compilation errors...$(NC)"
	@grep -A5 "shader\|SPIR-V\|MSL" $(LOGS_DIR)/*.log 2>/dev/null | head -100

# ============================================
# Utility targets
# ============================================

clean:
	rm -rf $(BUILD_DIR)/*
	cd $(MOLTENVK_DIR) && make clean || true
	cd $(DXVK_DIR)/build.64 && ninja clean || true

clean-logs:
	rm -f $(LOGS_DIR)/*.log

clear:
	@echo "$(YELLOW)Closing all Wine applications and shutting down wineserver...$(NC)"
	@WINEPREFIX=$(WINEPREFIX) wineserver -k 2>/dev/null || true
	@killall wine64 2>/dev/null || true
	@killall wine 2>/dev/null || true
	@killall wineserver 2>/dev/null || true
	@echo "$(GREEN)Wine processes terminated$(NC)"

# ============================================
# Development iteration helpers
# ============================================

# Quick rebuild and test cycle
iterate: build-mvk install-mvk run-fnv-debug
	@echo "$(GREEN)Iteration complete - check logs$(NC)"

# Find what's blocking FNV
diagnose:
	@echo "$(YELLOW)Diagnosing FNV issues...$(NC)"
	@echo ""
	@echo "=== Last crash/error ==="
	@tail -20 $(LOGS_DIR)/wine.log 2>/dev/null || echo "No wine log"
	@echo ""
	@echo "=== Unsupported Vulkan features ==="
	@grep -i "unsupported\|not implemented\|stub" $(LOGS_DIR)/*.log 2>/dev/null | sort -u | head -20
	@echo ""
	@echo "=== Extension requests ==="
	@grep -i "extension" $(LOGS_DIR)/*.log 2>/dev/null | grep -v "enabled" | sort -u | head -20
