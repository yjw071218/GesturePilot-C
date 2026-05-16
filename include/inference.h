/**
 * @file        inference.h
 * @brief       Python 추론 프로세스 연동 인터페이스
 * @details     tracker.py 프로세스를 실행하고 예측 결과를 읽어오는 기능을 정의한다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Company Name. All rights reserved.
 */
#pragma once

#include "gesture_types.h"

// 파이썬 추론 프로세스와의 입출력 상태를 보관함
typedef struct inference_ctx_t {
    unsigned long long frame_index; // 지금까지 읽은 예측 프레임 수
    char model_path[260];          // 사용 중인 모델 파일 경로
    void* handle;                  // 파이프/프로세스 핸들
} inference_ctx_t;

// 파이썬 추론 프로세스를 시작함
int inference_init(inference_ctx_t* context, const char* model_path);
// 다음 예측 결과 한 줄을 읽어 파싱함
prediction_t inference_run(inference_ctx_t* context);
// 파이썬 추론 프로세스를 종료함
void inference_shutdown(inference_ctx_t* context);

