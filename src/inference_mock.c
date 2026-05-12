#include "inference.h"

#include <string.h>

typedef struct scripted_frame_t {
    gesture_t gesture;
    float confidence;
} scripted_frame_t;

int inference_init(inference_ctx_t* context, const char* model_path) {
    if (context == NULL) {
        return 0;
    }

    memset(context, 0, sizeof(*context));
    if (model_path != NULL) {
        strncpy(context->model_path, model_path, sizeof(context->model_path) - 1);
    }
    return 1;
}

prediction_t inference_run(inference_ctx_t* context) {
    static const scripted_frame_t timeline[] = {
        {GESTURE_NONE, 0.30f}, {GESTURE_NONE, 0.35f}, {GESTURE_NONE, 0.25f}, {GESTURE_NONE, 0.20f},
        {GESTURE_POINT, 0.87f}, {GESTURE_POINT, 0.89f}, {GESTURE_POINT, 0.91f}, {GESTURE_POINT, 0.93f}, {GESTURE_POINT, 0.94f},
        {GESTURE_NONE, 0.30f}, {GESTURE_NONE, 0.30f},
        {GESTURE_V_SIGN, 0.86f}, {GESTURE_V_SIGN, 0.88f}, {GESTURE_V_SIGN, 0.91f}, {GESTURE_V_SIGN, 0.93f}, {GESTURE_V_SIGN, 0.94f},
        {GESTURE_NONE, 0.24f}, {GESTURE_NONE, 0.22f},
        {GESTURE_THREE, 0.82f}, {GESTURE_THREE, 0.84f}, {GESTURE_THREE, 0.88f}, {GESTURE_THREE, 0.90f}, {GESTURE_THREE, 0.92f},
        {GESTURE_OPEN_PALM, 0.88f}, {GESTURE_OPEN_PALM, 0.90f}, {GESTURE_OPEN_PALM, 0.93f}, {GESTURE_OPEN_PALM, 0.95f},
        {GESTURE_FOUR, 0.83f}, {GESTURE_FOUR, 0.85f}, {GESTURE_FOUR, 0.90f}, {GESTURE_FOUR, 0.92f}, {GESTURE_FOUR, 0.94f},
    };

    prediction_t result = {GESTURE_NONE, 0.0f};
    size_t index;
    size_t size = sizeof(timeline) / sizeof(timeline[0]);

    if (context == NULL || size == 0) {
        return result;
    }

    index = (size_t)(context->frame_index % size);
    context->frame_index++;
    result.gesture = timeline[index].gesture;
    result.confidence = timeline[index].confidence;
    return result;
}

void inference_shutdown(inference_ctx_t* context) {
    (void)context;
}

