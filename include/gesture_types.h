#pragma once

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

typedef enum action_t {
    ACTION_NONE = 0,
    ACTION_PLAY_PAUSE,
    ACTION_NEXT_SLIDE,
    ACTION_PREV_SLIDE,
    ACTION_VOLUME_UP,
    ACTION_VOLUME_DOWN,
    ACTION_CLICK_RIGHT,
    ACTION_TYPE_KEY
} action_t;

typedef struct prediction_t {
    gesture_t gesture;
    float confidence;
    float x;
    float y;
    int is_pinching;
    char key_name[16];
} prediction_t;

const char* gesture_to_string(gesture_t gesture);
gesture_t gesture_from_string(const char* text);

const char* action_to_string(action_t action);
action_t action_from_string(const char* text);

