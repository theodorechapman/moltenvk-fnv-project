/*
 * Geometry Shader Test Suite for MoltenVK
 * 
 * These tests verify geometry shader emulation.
 * Run with: make test-gs
 */

#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static VkInstance instance = VK_NULL_HANDLE;
static VkPhysicalDevice physicalDevice = VK_NULL_HANDLE;
static VkDevice device = VK_NULL_HANDLE;

int test_gs_feature_supported(void) {
    printf("TEST: gs_feature_supported\n");
    
    VkPhysicalDeviceFeatures features;
    vkGetPhysicalDeviceFeatures(physicalDevice, &features);
    
    if (features.geometryShader) {
        printf("  Geometry shaders: SUPPORTED\n");
        return 1;
    } else {
        printf("  Geometry shaders: NOT SUPPORTED\n");
        printf("  This is what needs to be implemented!\n");
        return 0;
    }
}

int test_gs_basic_passthrough(void) {
    printf("TEST: gs_basic_passthrough\n");
    
    // A passthrough GS: input triangle, output triangle unchanged
    // This is the simplest possible GS
    
    printf("  TODO: Implement passthrough GS test\n");
    return 0;
}

int test_gs_amplification(void) {
    printf("TEST: gs_amplification\n");
    
    // GS that outputs more primitives than input
    // e.g., input 1 triangle, output 2 triangles
    
    printf("  TODO: Implement amplification test\n");
    return 0;
}

int test_gs_culling(void) {
    printf("TEST: gs_culling\n");
    
    // GS that outputs fewer primitives than input
    // e.g., conditionally emit primitives
    
    printf("  TODO: Implement culling test\n");
    return 0;
}

int test_gs_layered_rendering(void) {
    printf("TEST: gs_layered_rendering\n");
    
    // GS that sets gl_Layer for layered framebuffers
    
    printf("  TODO: Implement layered rendering test\n");
    return 0;
}

int setup_vulkan(void) {
    VkApplicationInfo appInfo = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "GS Test",
        .apiVersion = VK_API_VERSION_1_2,
    };
    
    VkInstanceCreateInfo instanceInfo = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &appInfo,
    };
    
    if (vkCreateInstance(&instanceInfo, NULL, &instance) != VK_SUCCESS) {
        fprintf(stderr, "Failed to create instance\n");
        return 0;
    }
    
    uint32_t deviceCount = 1;
    vkEnumeratePhysicalDevices(instance, &deviceCount, &physicalDevice);
    
    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(physicalDevice, &props);
    printf("Using device: %s\n\n", props.deviceName);
    
    float priority = 1.0f;
    VkDeviceQueueCreateInfo queueInfo = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = 0,
        .queueCount = 1,
        .pQueuePriorities = &priority,
    };
    
    VkPhysicalDeviceFeatures features = {
        .geometryShader = VK_TRUE,
    };
    
    VkDeviceCreateInfo deviceInfo = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queueInfo,
        .pEnabledFeatures = &features,
    };
    
    VkResult result = vkCreateDevice(physicalDevice, &deviceInfo, NULL, &device);
    if (result != VK_SUCCESS) {
        printf("Note: Could not create device with GS (error %d)\n", result);
        printf("Creating device without GS...\n");
        
        features.geometryShader = VK_FALSE;
        vkCreateDevice(physicalDevice, &deviceInfo, NULL, &device);
    }
    
    return 1;
}

void cleanup_vulkan(void) {
    if (device) vkDestroyDevice(device, NULL);
    if (instance) vkDestroyInstance(instance, NULL);
}

int main(void) {
    printf("========================================\n");
    printf("Geometry Shader Test Suite\n");
    printf("========================================\n\n");
    
    if (!setup_vulkan()) return 1;
    
    int passed = 0, failed = 0;
    
    if (test_gs_feature_supported()) passed++; else failed++;
    if (test_gs_basic_passthrough()) passed++; else failed++;
    if (test_gs_amplification()) passed++; else failed++;
    if (test_gs_culling()) passed++; else failed++;
    if (test_gs_layered_rendering()) passed++; else failed++;
    
    printf("\n========================================\n");
    printf("Results: %d/5 PASSED, %d FAILED\n", passed, failed);
    printf("========================================\n");
    
    cleanup_vulkan();
    
    return (failed == 0) ? 0 : 1;
}
