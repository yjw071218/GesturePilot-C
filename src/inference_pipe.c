/**
 * @file        inference_pipe.c
 * @brief       Python 추론 프로세스 연동 구현
 * @details     tracker.py를 실행하고 표준 출력에서 예측 결과를 읽는다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Korea University. All rights reserved.
 */
#include "inference.h"  // Python 추론 프로세스 연동 선언

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

    // 이전 상태가 남지 않도록 컨텍스트를 비우고 모델 경로를 저장한다.
    memset(context, 0, sizeof(*context));
    if (model_path != NULL) {
        strncpy(context->model_path, model_path, sizeof(context->model_path) - 1);
    }

    // Python 트래커 프로세스를 실행함
    // 출력 버퍼링을 막기 위해 -u 옵션을 붙여 즉시 읽을 수 있게 함
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
        // tracker.py가 한 줄씩 내보낸 예측 문자열을 파싱한다.
        // 형식: 제스처이름 신뢰도 X Y 핀치마스크 스크롤변화 줌변화
        // 각 값은 공백으로 구분되어 한 줄에 전달된다.
        if (sscanf(line, "%63s %f %f %f %d %d %d", 
                   gesture_name, &result.confidence, &result.x, &result.y, 
                   &result.pinch_mask, &result.scroll_delta, &result.zoom_delta) == 7) {
            result.gesture = gesture_from_string(gesture_name);
            if (result.gesture == GESTURE_KEY && strncmp(gesture_name, "KEY_", 4) == 0) {
                strncpy(result.key_name, gesture_name + 4, sizeof(result.key_name) - 1);
            }
        } else {
            // 파싱 형식이 맞지 않으면 아무 제스처도 아닌 것으로 처리함
            result.gesture = GESTURE_NONE;
        }
    } else {
        // 출력이 끝났거나 읽기 오류가 발생한 경우
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
