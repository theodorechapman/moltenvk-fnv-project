# Unit tests Makefile
CC = clang
CFLAGS = -Wall -Wextra -g -O0
LDFLAGS = -lvulkan -framework Metal -framework Foundation

BUILD_DIR = ../../build/tests
SRC_DIR = .

TESTS = test_xfb test_gs test_robustness

.PHONY: all clean

all: $(BUILD_DIR) $(addprefix $(BUILD_DIR)/,$(TESTS))

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/test_xfb: test_xfb.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

$(BUILD_DIR)/test_gs: test_gs.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

$(BUILD_DIR)/test_robustness: test_robustness.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(BUILD_DIR)/test_*
