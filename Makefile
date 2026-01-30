# MoltenVK FNV Development Makefile
# Usage: make <target>

PROJECT_ROOT := $(shell pwd)
MOLTENVK_DIR := $(PROJECT_ROOT)/MoltenVK
DXVK_DIR := $(PROJECT_ROOT)/DXVK
WINEPREFIX := /Users/theo/.wine-fnv-mo2
FNV_DIR := $(WINEPREFIX)/drive_c/Games/Steam/steamapps/common/Fallout New Vegas
MO2_DIR := $(WINEPREFIX)/drive_c/MO2
LOGS_DIR := $(PROJECT_ROOT)/logs
BUILD_DIR := $(PROJECT_ROOT)/build

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

.PHONY: all build-mvk build-dxvk test run-fnv clean logs help

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
	@echo "  make run-fnv        - Run Fallout New Vegas"
	@echo "  make run-fnv-debug  - Run FNV with extra debugging"
	@echo "  make run-fnv-trace  - Run FNV with API tracing"
	@echo "  make run-fnv-nvse   - Run FNV with NVSE (for mods)"
	@echo "  make run-fnv-nvse-debug - Run FNV with NVSE + debugging"
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
	@echo "$(YELLOW)Building DXVK...$(NC)"
	cd $(DXVK_DIR)/build.64 && ninja
	@mkdir -p $(BUILD_DIR)/dxvk
	@cp $(DXVK_DIR)/build.64/src/d3d9/d3d9.dll $(BUILD_DIR)/dxvk/ 2>/dev/null || true
	@cp $(DXVK_DIR)/build.64/src/dxgi/dxgi.dll $(BUILD_DIR)/dxvk/ 2>/dev/null || true
	@echo "$(GREEN)DXVK built (check for errors above)$(NC)"

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

# ============================================
# Install/Setup targets
# ============================================

install-dxvk:
	@echo "$(YELLOW)Installing DXVK to Wine prefix...$(NC)"
	@mkdir -p $(WINEPREFIX)/drive_c/windows/system32
	@cp $(BUILD_DIR)/dxvk/*.dll $(WINEPREFIX)/drive_c/windows/system32/ 2>/dev/null || \
		echo "$(RED)No DXVK DLLs found - build DXVK first$(NC)"
	@echo "$(GREEN)DXVK installed$(NC)"

install-mvk:
	@echo "$(YELLOW)Installing MoltenVK...$(NC)"
	@sudo cp $(BUILD_DIR)/moltenvk/libMoltenVK.dylib /usr/local/lib/
	@echo "$(GREEN)MoltenVK installed$(NC)"

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
