#pragma once

#include <stddef.h>

#include "gesture_types.h"

#define GP_MAX_PATH 260
#define GP_MAX_BINDINGS 16

typedef struct gesture_binding_t {
    gesture_t gesture;
    action_t action;
} gesture_binding_t;

typedef struct app_config_t {
    float confidence_threshold;
    int stable_frames;
    int cooldown_ms;
    int loop_interval_ms;
    int total_frames;
    int dry_run;
    char model_path[GP_MAX_PATH];

    size_t binding_count;
    gesture_binding_t bindings[GP_MAX_BINDINGS];
} app_config_t;

void config_set_defaults(app_config_t* out_config);
int config_load(const char* path, app_config_t* out_config, char* error_buffer, size_t error_buffer_size);

