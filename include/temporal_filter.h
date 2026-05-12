#pragma once

#include <stddef.h>

#include "gesture_types.h"

typedef struct temporal_filter_t {
    gesture_t history[64];
    size_t cursor;
    size_t count;

    int stable_frames;
    float confidence_threshold;
    int cooldown_ms;

    unsigned long long last_emit_ms;
    gesture_t last_emitted;
} temporal_filter_t;

void temporal_filter_init(temporal_filter_t* filter, int stable_frames, float confidence_threshold, int cooldown_ms);
int temporal_filter_update(temporal_filter_t* filter, prediction_t prediction, unsigned long long now_ms, gesture_t* out_stable_gesture);

