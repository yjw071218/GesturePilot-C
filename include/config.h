/**
 * @file        config.h
 * @brief       실행 설정과 INI 파싱 인터페이스
 * @details     기본값 초기화와 설정 파일 로드를 담당한다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Company Name. All rights reserved.
 */
#pragma once

#include <stddef.h>

#include "gesture_types.h"

// 모델/설정 파일 경로의 최대 길이
#define GP_MAX_PATH 260
// 허용할 제스처 바인딩의 최대 개수
#define GP_MAX_BINDINGS 16

// 한 제스처가 어떤 액션으로 연결되는지 저장함
typedef struct gesture_binding_t {
    gesture_t gesture; // 입력 제스처
    action_t action;   // 대응 액션
} gesture_binding_t;

// 프로그램 전체 동작을 제어하는 설정값 묶음
typedef struct app_config_t {
    float confidence_threshold; // 예측을 신뢰할 최소 확률
    int stable_frames;          // 같은 제스처가 연속으로 나와야 하는 횟수
    int cooldown_ms;            // 같은 액션 재실행 전 대기 시간
    int loop_interval_ms;       // 메인 루프 간격
    int total_frames;           // 전체 처리 프레임 수 제한
    int dry_run;                // 실제 입력 대신 시뮬레이션만 할지 여부
    char model_path[GP_MAX_PATH]; // ONNX 모델 경로

    size_t binding_count;                   // 현재 등록된 바인딩 수
    gesture_binding_t bindings[GP_MAX_BINDINGS]; // 제스처-액션 바인딩 배열
} app_config_t;

// 기본 동작값으로 설정 구조체를 초기화함
void config_set_defaults(app_config_t* out_config);
// INI 설정 파일을 읽어 실행 설정을 채움
int config_load(const char* path, app_config_t* out_config, char* error_buffer, size_t error_buffer_size);

