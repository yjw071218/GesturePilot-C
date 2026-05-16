// Python tracker 프로세스를 실행하고 예측 라인을 읽는다.
#include "inference.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifdef _WIN32
#define POPEN _popen
#define PCLOSE _pclose
#else
#define POPEN popen
#define PCLOSE pclose
#endif

int inference_init(inference_ctx_t* context, const char* model_path) {
    if (context == NULL) {
        return 0;
    }

    memset(context, 0, sizeof(*context));
    if (model_path != NULL) {
        strncpy(context->model_path, model_path, sizeof(context->model_path) - 1);
    }

    // Launch python script
    // Unbuffered output from python is needed so we pass -u
    FILE* pipe = POPEN("python -u scripts/tracker.py", "r");
    if (!pipe) {
        fprintf(stderr, "Failed to start python tracker.py\n");
        return 0;
    }
    context->handle = (void*)pipe;
    return 1;
}

prediction_t inference_run(inference_ctx_t* context) {
    prediction_t result;
    FILE* pipe;
    char line[256];
    char gesture_name[64];

    memset(&result, 0, sizeof(result));
    result.gesture = GESTURE_NONE;
    result.x = 0.5f;
    result.y = 0.5f;

    if (context == NULL || context->handle == NULL) {
        return result;
    }

    pipe = (FILE*)context->handle;
    if (fgets(line, sizeof(line), pipe) != NULL) {
        // Format: GESTURE_NAME CONFIDENCE X Y PINCH_MASK SCROLL_DELTA ZOOM_DELTA
        if (sscanf(line, "%63s %f %f %f %d %d %d", 
                   gesture_name, &result.confidence, &result.x, &result.y, 
                   &result.pinch_mask, &result.scroll_delta, &result.zoom_delta) == 7) {
            result.gesture = gesture_from_string(gesture_name);
            if (result.gesture == GESTURE_KEY && strncmp(gesture_name, "KEY_", 4) == 0) {
                strncpy(result.key_name, gesture_name + 4, sizeof(result.key_name) - 1);
            }
        } else {
            result.gesture = GESTURE_NONE;
        }
    } else {
        // EOF or error
        result.gesture = GESTURE_NONE;
        result.confidence = -1.0f;
    }
    context->frame_index++;
    return result;
}

void inference_shutdown(inference_ctx_t* context) {
    if (context != NULL && context->handle != NULL) {
        PCLOSE((FILE*)context->handle);
        context->handle = NULL;
    }
}
