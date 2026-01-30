/*
 * Transform Feedback Test Suite for MoltenVK
 * 
 * These tests verify VK_EXT_transform_feedback emulation.
 * Run with: make test-xfb
 * 
 * Test progression:
 * 1. test_xfb_extension_present - Does MoltenVK advertise the extension?
 * 2. test_xfb_basic_capture - Can we capture vertex output?
 * 3. test_xfb_query_primitives - Do primitive counts work?
 * 4. test_xfb_pause_resume - Does pause/resume work?
 * 5. test_xfb_overflow - Is overflow handled correctly?
 */

#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define TEST_ASSERT(cond, msg) do { \
    if (!(cond)) { \
        fprintf(stderr, "FAILED: %s\n  %s:%d\n", msg, __FILE__, __LINE__); \
        return 0; \
    } \
} while(0)

#define TEST_VK(call) do { \
    VkResult _r = (call); \
    if (_r != VK_SUCCESS) { \
        fprintf(stderr, "FAILED: %s returned %d\n  %s:%d\n", #call, _r, __FILE__, __LINE__); \
        return 0; \
    } \
} while(0)

// Global Vulkan state
static VkInstance instance = VK_NULL_HANDLE;
static VkPhysicalDevice physicalDevice = VK_NULL_HANDLE;
static VkDevice device = VK_NULL_HANDLE;
static VkQueue queue = VK_NULL_HANDLE;
static uint32_t queueFamily = 0;

// Extension function pointers
static PFN_vkCmdBeginTransformFeedbackEXT vkCmdBeginTransformFeedbackEXT = NULL;
static PFN_vkCmdEndTransformFeedbackEXT vkCmdEndTransformFeedbackEXT = NULL;
static PFN_vkCmdBindTransformFeedbackBuffersEXT vkCmdBindTransformFeedbackBuffersEXT = NULL;

/* ============================================
 * Test: Extension Present
 * ============================================ */
int test_xfb_extension_present(void) {
    printf("TEST: xfb_extension_present\n");
    
    uint32_t extensionCount = 0;
    vkEnumerateDeviceExtensionProperties(physicalDevice, NULL, &extensionCount, NULL);
    
    VkExtensionProperties* extensions = malloc(extensionCount * sizeof(VkExtensionProperties));
    vkEnumerateDeviceExtensionProperties(physicalDevice, NULL, &extensionCount, extensions);
    
    int found = 0;
    for (uint32_t i = 0; i < extensionCount; i++) {
        if (strcmp(extensions[i].extensionName, VK_EXT_TRANSFORM_FEEDBACK_EXTENSION_NAME) == 0) {
            found = 1;
            printf("  Found VK_EXT_transform_feedback (spec version %d)\n", 
                   extensions[i].specVersion);
            break;
        }
    }
    
    free(extensions);
    
    if (!found) {
        printf("  VK_EXT_transform_feedback NOT FOUND\n");
        printf("  This is the first thing to implement!\n");
        return 0;
    }
    
    return 1;
}

/* ============================================
 * Test: Basic Vertex Capture
 * ============================================ */
int test_xfb_basic_capture(void) {
    printf("TEST: xfb_basic_capture\n");
    
    // Skip if extension not present
    if (!vkCmdBeginTransformFeedbackEXT) {
        printf("  SKIPPED: Extension functions not loaded\n");
        return 0;
    }
    
    // Create a simple vertex shader that outputs position
    // Input: vec4 position
    // Output: vec4 position (captured via XFB)
    
    // ... shader creation code ...
    
    // Create XFB buffer
    VkBufferCreateInfo bufferInfo = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = 1024,
        .usage = VK_BUFFER_USAGE_TRANSFORM_FEEDBACK_BUFFER_BIT_EXT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
    };
    
    VkBuffer xfbBuffer;
    VkResult result = vkCreateBuffer(device, &bufferInfo, NULL, &xfbBuffer);
    
    if (result != VK_SUCCESS) {
        printf("  FAILED: Could not create XFB buffer (error %d)\n", result);
        printf("  MoltenVK may not support TRANSFORM_FEEDBACK_BUFFER_BIT\n");
        return 0;
    }
    
    printf("  XFB buffer created successfully\n");
    
    // TODO: Complete test with actual rendering and verification
    
    vkDestroyBuffer(device, xfbBuffer, NULL);
    return 1;
}

/* ============================================
 * Test: Query Primitives Written
 * ============================================ */
int test_xfb_query_primitives(void) {
    printf("TEST: xfb_query_primitives\n");
    
    // Create query pool for XFB statistics
    VkQueryPoolCreateInfo queryInfo = {
        .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
        .queryType = VK_QUERY_TYPE_TRANSFORM_FEEDBACK_STREAM_EXT,
        .queryCount = 1,
    };
    
    VkQueryPool queryPool;
    VkResult result = vkCreateQueryPool(device, &queryInfo, NULL, &queryPool);
    
    if (result != VK_SUCCESS) {
        printf("  FAILED: Could not create XFB query pool (error %d)\n", result);
        return 0;
    }
    
    printf("  XFB query pool created\n");
    
    vkDestroyQueryPool(device, queryPool, NULL);
    return 1;
}

/* ============================================
 * Test: Pause/Resume
 * ============================================ */
int test_xfb_pause_resume(void) {
    printf("TEST: xfb_pause_resume\n");
    printf("  TODO: Implement pause/resume test\n");
    return 0;
}

/* ============================================
 * Test: Buffer Overflow
 * ============================================ */
int test_xfb_overflow(void) {
    printf("TEST: xfb_overflow\n");
    printf("  TODO: Implement overflow test\n");
    return 0;
}

/* ============================================
 * Vulkan Setup
 * ============================================ */
int setup_vulkan(void) {
    // Create instance
    VkApplicationInfo appInfo = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "XFB Test",
        .applicationVersion = VK_MAKE_VERSION(1, 0, 0),
        .pEngineName = "Test",
        .engineVersion = VK_MAKE_VERSION(1, 0, 0),
        .apiVersion = VK_API_VERSION_1_2,
    };
    
    const char* layers[] = { "VK_LAYER_KHRONOS_validation" };
    
    VkInstanceCreateInfo instanceInfo = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &appInfo,
        .enabledLayerCount = 1,
        .ppEnabledLayerNames = layers,
    };
    
    if (vkCreateInstance(&instanceInfo, NULL, &instance) != VK_SUCCESS) {
        fprintf(stderr, "Failed to create Vulkan instance\n");
        return 0;
    }
    
    // Get physical device
    uint32_t deviceCount = 1;
    vkEnumeratePhysicalDevices(instance, &deviceCount, &physicalDevice);
    
    if (physicalDevice == VK_NULL_HANDLE) {
        fprintf(stderr, "No Vulkan device found\n");
        return 0;
    }
    
    // Print device info
    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(physicalDevice, &props);
    printf("Using device: %s\n", props.deviceName);
    printf("Driver version: %d.%d.%d\n", 
           VK_VERSION_MAJOR(props.driverVersion),
           VK_VERSION_MINOR(props.driverVersion),
           VK_VERSION_PATCH(props.driverVersion));
    
    // Find queue family
    uint32_t queueFamilyCount = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice, &queueFamilyCount, NULL);
    VkQueueFamilyProperties* queueFamilies = malloc(queueFamilyCount * sizeof(VkQueueFamilyProperties));
    vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice, &queueFamilyCount, queueFamilies);
    
    for (uint32_t i = 0; i < queueFamilyCount; i++) {
        if (queueFamilies[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) {
            queueFamily = i;
            break;
        }
    }
    free(queueFamilies);
    
    // Create device with XFB extension (if available)
    float queuePriority = 1.0f;
    VkDeviceQueueCreateInfo queueInfo = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = queueFamily,
        .queueCount = 1,
        .pQueuePriorities = &queuePriority,
    };
    
    const char* deviceExtensions[] = {
        VK_EXT_TRANSFORM_FEEDBACK_EXTENSION_NAME,
    };
    
    VkPhysicalDeviceTransformFeedbackFeaturesEXT xfbFeatures = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_TRANSFORM_FEEDBACK_FEATURES_EXT,
        .transformFeedback = VK_TRUE,
        .geometryStreams = VK_TRUE,
    };
    
    VkDeviceCreateInfo deviceInfo = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .pNext = &xfbFeatures,
        .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queueInfo,
        .enabledExtensionCount = 1,
        .ppEnabledExtensionNames = deviceExtensions,
    };
    
    VkResult result = vkCreateDevice(physicalDevice, &deviceInfo, NULL, &device);
    
    if (result != VK_SUCCESS) {
        printf("Note: Could not create device with XFB extension (error %d)\n", result);
        printf("Creating device without XFB for basic tests...\n");
        
        deviceInfo.pNext = NULL;
        deviceInfo.enabledExtensionCount = 0;
        deviceInfo.ppEnabledExtensionNames = NULL;
        
        if (vkCreateDevice(physicalDevice, &deviceInfo, NULL, &device) != VK_SUCCESS) {
            fprintf(stderr, "Failed to create Vulkan device\n");
            return 0;
        }
    } else {
        // Load extension functions
        vkCmdBeginTransformFeedbackEXT = (PFN_vkCmdBeginTransformFeedbackEXT)
            vkGetDeviceProcAddr(device, "vkCmdBeginTransformFeedbackEXT");
        vkCmdEndTransformFeedbackEXT = (PFN_vkCmdEndTransformFeedbackEXT)
            vkGetDeviceProcAddr(device, "vkCmdEndTransformFeedbackEXT");
        vkCmdBindTransformFeedbackBuffersEXT = (PFN_vkCmdBindTransformFeedbackBuffersEXT)
            vkGetDeviceProcAddr(device, "vkCmdBindTransformFeedbackBuffersEXT");
            
        printf("XFB extension enabled and functions loaded\n");
    }
    
    vkGetDeviceQueue(device, queueFamily, 0, &queue);
    
    return 1;
}

void cleanup_vulkan(void) {
    if (device) vkDestroyDevice(device, NULL);
    if (instance) vkDestroyInstance(instance, NULL);
}

/* ============================================
 * Main
 * ============================================ */
int main(int argc, char** argv) {
    printf("========================================\n");
    printf("Transform Feedback Test Suite\n");
    printf("========================================\n\n");
    
    if (!setup_vulkan()) {
        return 1;
    }
    
    int passed = 0;
    int failed = 0;
    int total = 5;
    
    // Run tests in order of complexity
    if (test_xfb_extension_present()) passed++; else failed++;
    if (test_xfb_basic_capture()) passed++; else failed++;
    if (test_xfb_query_primitives()) passed++; else failed++;
    if (test_xfb_pause_resume()) passed++; else failed++;
    if (test_xfb_overflow()) passed++; else failed++;
    
    printf("\n========================================\n");
    printf("Results: %d/%d PASSED, %d FAILED\n", passed, total, failed);
    printf("========================================\n");
    
    cleanup_vulkan();
    
    if (failed == 0) {
        printf("PASSED\n");
        return 0;
    } else {
        printf("FAILED\n");
        return 1;
    }
}
