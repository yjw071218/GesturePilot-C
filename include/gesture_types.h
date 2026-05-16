/**
 * @file        gesture_types.h
 * @brief       손동작, 액션, 추론 결과의 공통 타입 정의
 * @details     C 코어와 Python 트래커가 공유하는 열거형과 예측 구조체를 제공한다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Company Name. All rights reserved.
 */
#pragma once

// 카메라/모델이 인식하는 손동작 종류
typedef enum gesture_t {
    GESTURE_NONE = 0,
    GESTURE_FIST,
    GESTURE_POINT,
    GESTURE_V_SIGN,
    GESTURE_THREE,
    GESTURE_FOUR,
    GESTURE_OPEN_PALM,
    GESTURE_KEY,
    GESTURE_UNKNOWN
} gesture_t;

// 제스처가 트리거할 수 있는 시스템 액션 종류
typedef enum action_t {
    ACTION_NONE = 0,
    ACTION_PLAY_PAUSE,
    ACTION_NEXT_SLIDE,
    ACTION_PREV_SLIDE,
    ACTION_VOLUME_UP,
    ACTION_VOLUME_DOWN,
    ACTION_CLICK_RIGHT
} action_t;

// 파이썬 트래커가 한 프레임마다 전달하는 예측 결과
typedef struct prediction_t {
    gesture_t gesture;   // 예측된 제스처
    float confidence;    // 예측 신뢰도
    float x;             // 마우스 이동용 정규화 X 좌표
    float y;             // 마우스 이동용 정규화 Y 좌표
    int pinch_mask;      // 좌클릭/우클릭/고정 상태를 담는 비트마스크
    char key_name[16];   // 특수 키 입력용 키 이름
    int scroll_delta;    // 세로 스크롤 변화량
    int zoom_delta;      // 줌 변화량
} prediction_t;

// 제스처를 문자열로 변환함
const char* gesture_to_string(gesture_t gesture);
// 문자열을 제스처 열거형으로 변환함
gesture_t gesture_from_string(const char* text);

// 액션을 문자열로 변환함
const char* action_to_string(action_t action);
// 문자열을 액션 열거형으로 변환함
action_t action_from_string(const char* text);
