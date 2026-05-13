#pragma once

#include "gesture_types.h"

typedef struct inference_ctx_t {
    unsigned long long frame_index;
    char model_path[260];
    void* handle;
} inference_ctx_t;

int inference_init(inference_ctx_t* context, const char* model_path);
prediction_t inference_run(inference_ctx_t* context);
void inference_shutdown(inference_ctx_t* context);

