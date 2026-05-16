// 연속 예측을 누적해 안정적인 제스처만 내보낸다.
#include "temporal_filter.h"

#include <string.h>

static size_t history_index(const temporal_filter_t* filter, size_t reverse_index) {
    size_t latest = (filter->cursor + 64 - 1) % 64;
    return (latest + 64 - reverse_index) % 64;
}

void temporal_filter_init(temporal_filter_t* filter, int stable_frames, float confidence_threshold, int cooldown_ms) {
    if (filter == NULL) {
        return;
    }

    memset(filter, 0, sizeof(*filter));
    filter->stable_frames = stable_frames;
    filter->confidence_threshold = confidence_threshold;
    filter->cooldown_ms = cooldown_ms;
    filter->last_emitted = GESTURE_UNKNOWN;
}

static void push_history(temporal_filter_t* filter, gesture_t gesture) {
    filter->history[filter->cursor] = gesture;
    filter->cursor = (filter->cursor + 1) % 64;
    if (filter->count < 64) {
        filter->count++;
    }
}

static int recent_streak(const temporal_filter_t* filter, gesture_t gesture) {
    size_t reverse_index;
    int streak = 0;

    for (reverse_index = 0; reverse_index < filter->count; ++reverse_index) {
        size_t index = history_index(filter, reverse_index);
        if (filter->history[index] != gesture) {
            break;
        }
        streak++;
    }

    return streak;
}

int temporal_filter_update(temporal_filter_t* filter, prediction_t prediction, unsigned long long now_ms, gesture_t* out_stable_gesture) {
    int streak;

    if (filter == NULL || out_stable_gesture == NULL) {
        return 0;
    }

    if (prediction.gesture == GESTURE_UNKNOWN ||
        prediction.gesture == GESTURE_NONE ||
        prediction.confidence < filter->confidence_threshold) {
        return 0;
    }

    push_history(filter, prediction.gesture);
    streak = recent_streak(filter, prediction.gesture);
    if (streak < filter->stable_frames) {
        return 0;
    }

    if (filter->last_emitted == prediction.gesture &&
        now_ms - filter->last_emit_ms < (unsigned long long)filter->cooldown_ms) {
        return 0;
    }

    filter->last_emit_ms = now_ms;
    filter->last_emitted = prediction.gesture;
    *out_stable_gesture = prediction.gesture;
    return 1;
}

