/**
 * @file        gesture_types.c
 * @brief       손동작과 액션 문자열 변환 구현
 * @details     열거형 값을 사람이 읽을 수 있는 문자열과 상호 변환한다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Korea University. All rights reserved.
 */
#include "gesture_types.h"

#include <ctype.h>
#include <string.h>

typedef struct named_gesture_t {
    const char* name;
    gesture_t value;
} named_gesture_t;

typedef struct named_action_t {
    const char* name;
    action_t value;
} named_action_t;

static int text_equals_ignore_case(const char* left, const char* right) {
    while (*left != '\0' && *right != '\0') {
        if (tolower((unsigned char)*left) != tolower((unsigned char)*right)) {
            return 0;
        }
        left++;
        right++;
    }
    return *left == '\0' && *right == '\0';
}

const char* gesture_to_string(gesture_t gesture) {
    switch (gesture) {
        case GESTURE_NONE: return "none";
        case GESTURE_FIST: return "fist";
        case GESTURE_POINT: return "point";
        case GESTURE_V_SIGN: return "v_sign";
        case GESTURE_THREE: return "three";
        case GESTURE_FOUR: return "four";
        case GESTURE_OPEN_PALM: return "open_palm";
        case GESTURE_KEY: return "key";
        default: return "unknown";
    }
}

gesture_t gesture_from_string(const char* text) {
    static const named_gesture_t map[] = {
        {"none", GESTURE_NONE},
        {"fist", GESTURE_FIST},
        {"point", GESTURE_POINT},
        {"v_sign", GESTURE_V_SIGN},
        {"three", GESTURE_THREE},
        {"four", GESTURE_FOUR},
        {"open_palm", GESTURE_OPEN_PALM},
        {"key", GESTURE_KEY}
    };

    size_t index;
    if (text == NULL) {
        return GESTURE_UNKNOWN;
    }

    if (strncmp(text, "KEY_", 4) == 0) {
        return GESTURE_KEY;
    }

    for (index = 0; index < sizeof(map) / sizeof(map[0]); ++index) {
        if (text_equals_ignore_case(text, map[index].name)) {
            return map[index].value;
        }
    }

    return GESTURE_UNKNOWN;
}

const char* action_to_string(action_t action) {
    switch (action) {
        case ACTION_NONE: return "none";
        case ACTION_PLAY_PAUSE: return "play_pause";
        case ACTION_NEXT_SLIDE: return "next_slide";
        case ACTION_PREV_SLIDE: return "prev_slide";
        case ACTION_VOLUME_UP: return "volume_up";
        case ACTION_VOLUME_DOWN: return "volume_down";
        case ACTION_CLICK_RIGHT: return "click_right";
        default: return "none";
    }
}

action_t action_from_string(const char* text) {
    static const named_action_t map[] = {
        {"none", ACTION_NONE},
        {"play_pause", ACTION_PLAY_PAUSE},
        {"next_slide", ACTION_NEXT_SLIDE},
        {"prev_slide", ACTION_PREV_SLIDE},
        {"volume_up", ACTION_VOLUME_UP},
        {"volume_down", ACTION_VOLUME_DOWN},
        {"click_right", ACTION_CLICK_RIGHT}
    };

    size_t index;
    if (text == NULL) {
        return ACTION_NONE;
    }

    for (index = 0; index < sizeof(map) / sizeof(map[0]); ++index) {
        if (text_equals_ignore_case(text, map[index].name)) {
            return map[index].value;
        }
    }

    return ACTION_NONE;
}

