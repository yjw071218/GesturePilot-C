#pragma once

// 인식할 제스처 종류 열거형
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

// 제스처에 대응하는 액션 종류 열거형
typedef enum action_t {
    ACTION_NONE = 0,
    ACTION_PLAY_PAUSE,
    ACTION_NEXT_SLIDE,
    ACTION_PREV_SLIDE,
    ACTION_VOLUME_UP,
    ACTION_VOLUME_DOWN,
    ACTION_CLICK_RIGHT
} action_t;

// 모델 예측 결과를 담는 구조체
typedef struct prediction_t {
    gesture_t gesture;     // 예측된 제스처
    float confidence;      // 예측 신뢰도
    float x;               // X 좌표
    float y;               // Y 좌표
    int pinch_mask;        // 핀치 동작 마스크
    char key_name[16];     // 눌린 키 이름
    int scroll_delta;      // 스크롤 변화량
    int zoom_delta;        // 줌 변화량
} prediction_t;

// 제스처를 문자열로 변환함
const char* gesture_to_string(gesture_t gesture);
// 문자열을 제스처 열거형으로 변환함
gesture_t gesture_from_string(const char* text);

// 액션을 문자열로 변환함
const char* action_to_string(action_t action);
// 문자열을 액션 열거형으로 변환함
action_t action_from_string(const char* text);
