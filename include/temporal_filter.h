/**
 * @file        temporal_filter.h
 * @brief       연속 예측 안정화용 시간 필터 인터페이스
 * @details     안정 프레임과 쿨다운을 사용해 제스처 흔들림을 줄인다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Korea University. All rights reserved.
 */
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

