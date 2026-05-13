#include "action_mapper.h"
#include "config.h"
#include "inference.h"
#include "input_injector.h"
#include "temporal_filter.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
static unsigned long long now_ms(void) {
    return GetTickCount64();
}
static void sleep_ms(unsigned int ms) {
    Sleep(ms);
}
#else
#include <time.h>
static unsigned long long now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (unsigned long long)ts.tv_sec * 1000ULL + (unsigned long long)(ts.tv_nsec / 1000000ULL);
}
static void sleep_ms(unsigned int ms) {
    struct timespec req;
    req.tv_sec = ms / 1000;
    req.tv_nsec = (long)(ms % 1000) * 1000000L;
    nanosleep(&req, NULL);
}
#endif

static void print_usage(void) {
    printf("Usage: gesturepilot [--config <path>] [--frames <count>] [--dry-run <0|1>]\n");
}

int main(int argc, char** argv) {
    app_config_t config;
    temporal_filter_t filter;
    inference_ctx_t inference_context;
    char config_path[GP_MAX_PATH] = "config\\gesturepilot.sample.ini";
    char error_buffer[256];
    int frames_override = -1;
    int dry_run_override = -1;
    int index;

    config_set_defaults(&config);

    for (index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--config") == 0 && index + 1 < argc) {
            strncpy(config_path, argv[++index], GP_MAX_PATH - 1);
            config_path[GP_MAX_PATH - 1] = '\0';
        } else if (strcmp(argv[index], "--frames") == 0 && index + 1 < argc) {
            frames_override = atoi(argv[++index]);
        } else if (strcmp(argv[index], "--dry-run") == 0 && index + 1 < argc) {
            dry_run_override = atoi(argv[++index]) ? 1 : 0;
        } else if (strcmp(argv[index], "--help") == 0) {
            print_usage();
            return 0;
        } else {
            print_usage();
            return 1;
        }
    }

    if (!config_load(config_path, &config, error_buffer, sizeof(error_buffer))) {
        printf("Config warning: %s (fallback defaults kept where needed)\n", error_buffer);
    }
    if (frames_override >= 0) {
        config.total_frames = frames_override;
    }
    if (dry_run_override >= 0) {
        config.dry_run = dry_run_override;
    }

    if (!inference_init(&inference_context, config.model_path)) {
        fprintf(stderr, "Failed to initialize inference backend.\n");
        return 1;
    }

    temporal_filter_init(&filter, config.stable_frames, config.confidence_threshold, config.cooldown_ms);

    printf("GesturePilot-C started\n");
    printf("  config: %s\n", config_path);
    printf("  model : %s\n", config.model_path);
    printf("  dry_run=%d stable_frames=%d threshold=%.2f cooldown=%dms frames=%d\n",
           config.dry_run, config.stable_frames, config.confidence_threshold, config.cooldown_ms, config.total_frames);

    for (index = 0; config.total_frames <= 0 || index < config.total_frames; ++index) {
        prediction_t prediction = inference_run(&inference_context);
        
        // If confidence is negative, it might indicate the pipe is closed or tracking failed permanently
        if (prediction.gesture == GESTURE_NONE && prediction.confidence < 0.0f) {
            break;
        }

        gesture_t stable_gesture = GESTURE_UNKNOWN;
        unsigned long long timestamp = now_ms();

        printf("[frame %04d] pred=%-10s conf=%.2f x=%.2f y=%.2f pinch=%d key=%s\n", 
               index + 1, gesture_to_string(prediction.gesture), prediction.confidence, 
               prediction.x, prediction.y, prediction.is_pinching, prediction.key_name);

        if (prediction.confidence > 0.0f) {
            input_injector_update_mouse(prediction.x, prediction.y, prediction.is_pinching, config.dry_run);
        }

        // Handle typing directly without temporal filtering for responsiveness
        if (prediction.gesture == GESTURE_KEY && prediction.confidence > 0.8f) {
            input_injector_type_key(prediction.key_name, config.dry_run);
        } else if (temporal_filter_update(&filter, prediction, timestamp, &stable_gesture)) {
            action_t action = action_mapper_resolve(&config, stable_gesture);
            printf("  -> stable=%s action=%s\n", gesture_to_string(stable_gesture), action_to_string(action));
            if (!input_injector_execute(action, config.dry_run)) {
                fprintf(stderr, "Input injection failed for action=%s\n", action_to_string(action));
            }
        }

        sleep_ms((unsigned int)config.loop_interval_ms);
    }

    inference_shutdown(&inference_context);
    printf("GesturePilot-C finished.\n");
    return 0;
}

