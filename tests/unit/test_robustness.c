/*
 * Robustness Feature Test Suite for MoltenVK
 * 
 * Tests VK_EXT_robustness2 features needed by DXVK d3d9
 */

#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>

static VkInstance instance = VK_NULL_HANDLE;
static VkPhysicalDevice physicalDevice = VK_NULL_HANDLE;

int test_robustness2_extension(void) {
    printf("TEST: robustness2_extension\n");
    
    uint32_t extensionCount = 0;
    vkEnumerateDeviceExtensionProperties(physicalDevice, NULL, &extensionCount, NULL);
    
    VkExtensionProperties* extensions = malloc(extensionCount * sizeof(VkExtensionProperties));
    vkEnumerateDeviceExtensionProperties(physicalDevice, NULL, &extensionCount, extensions);
    
    int found = 0;
    for (uint32_t i = 0; i < extensionCount; i++) {
        if (strcmp(extensions[i].extensionName, "VK_EXT_robustness2") == 0) {
            found = 1;
            break;
        }
    }
    free(extensions);
    
    if (found) {
        printf("  VK_EXT_robustness2: PRESENT\n");
    } else {
        printf("  VK_EXT_robustness2: MISSING\n");
    }
    
    return found;
}

int test_null_descriptor(void) {
    printf("TEST: null_descriptor\n");
    
    // Check if nullDescriptor feature is supported
    // DXVK d3d9 uses this for unbound texture slots
    
    VkPhysicalDeviceRobustness2FeaturesEXT robustness2 = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ROBUSTNESS_2_FEATURES_EXT,
    };
    
    VkPhysicalDeviceFeatures2 features2 = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
        .pNext = &robustness2,
    };
    
    vkGetPhysicalDeviceFeatures2(physicalDevice, &features2);
    
    if (robustness2.nullDescriptor) {
        printf("  nullDescriptor: SUPPORTED\n");
        return 1;
    } else {
        printf("  nullDescriptor: NOT SUPPORTED\n");
        printf("  DXVK d3d9 needs this for unbound textures\n");
        return 0;
    }
}

int setup_vulkan(void) {
    VkApplicationInfo appInfo = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "Robustness Test",
        .apiVersion = VK_API_VERSION_1_2,
    };
    
    VkInstanceCreateInfo instanceInfo = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &appInfo,
    };
    
    if (vkCreateInstance(&instanceInfo, NULL, &instance) != VK_SUCCESS) {
        return 0;
    }
    
    uint32_t deviceCount = 1;
    vkEnumeratePhysicalDevices(instance, &deviceCount, &physicalDevice);
    
    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(physicalDevice, &props);
    printf("Using device: %s\n\n", props.deviceName);
    
    return 1;
}

void cleanup_vulkan(void) {
    if (instance) vkDestroyInstance(instance, NULL);
}

int main(void) {
    printf("========================================\n");
    printf("Robustness Feature Test Suite\n");
    printf("========================================\n\n");
    
    if (!setup_vulkan()) return 1;
    
    int passed = 0, failed = 0;
    
    if (test_robustness2_extension()) passed++; else failed++;
    if (test_null_descriptor()) passed++; else failed++;
    
    printf("\n========================================\n");
    printf("Results: %d/2 PASSED, %d FAILED\n", passed, failed);
    printf("========================================\n");
    
    cleanup_vulkan();
    
    return (failed == 0) ? 0 : 1;
}
