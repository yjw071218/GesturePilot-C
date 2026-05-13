#include "input_injector.h"

#include <stdio.h>
#include <windows.h>
#include <math.h>

static WORD action_to_vk(action_t action) {
    switch (action) {
        case ACTION_PLAY_PAUSE: return VK_MEDIA_PLAY_PAUSE;
        case ACTION_NEXT_SLIDE: return VK_RIGHT;
        case ACTION_PREV_SLIDE: return VK_LEFT;
        case ACTION_VOLUME_UP: return VK_VOLUME_UP;
        case ACTION_VOLUME_DOWN: return VK_VOLUME_DOWN;
        default: return 0;
    }
}

static int last_pinch_mask = 0;
static float smoothed_x = 0.5f;
static float smoothed_y = 0.5f;

static ULONGLONG left_pinch_start_time = 0;
static float initial_pinch_x = 0;
static float initial_pinch_y = 0;
static int is_drag_mode = 0;

#define DRAG_TIME_THRESHOLD_MS 300
#define DRAG_DIST_THRESHOLD 0.02f

void input_injector_update_mouse(float x, float y, int pinch_mask, int scroll_delta, int zoom_delta, int dry_run) {
    if (dry_run) return;

    // In this mode, Python handles all actions (clicks, scrolls, zoom).
    // C side ONLY handles smooth movement.
    // pinch_mask bit 4 is the 'freeze' signal from Python.
    // pinch_mask bit 0 is 'left_down' (for alpha smoothing adjustment).
    
    int left_now = pinch_mask & 1;
    int freeze_raw = (pinch_mask >> 4) & 1;

    // Movement Calculation
    int should_move = !freeze_raw;
    
    // Adaptive Smoothing: 
    // Higher jitter during movement, lower jitter (more lag) during precise actions.
    // We use a dynamic alpha based on whether a click/pinch is active.
    float target_alpha = 0.25f; // Reverted to fixed responsive alpha
    
    if (left_now) {
        target_alpha = 0.03f; // Precision lock for dragging/clicking
    } else if (freeze_raw) {
        target_alpha = 0.01f; // Heavy lock-on during right-click/scroll
    }

    // Exponential moving average for smoothness
    smoothed_x = smoothed_x * (1.0f - target_alpha) + x * target_alpha;
    smoothed_y = smoothed_y * (1.0f - target_alpha) + y * target_alpha;

    if (should_move) {
        // Precise sub-pixel to absolute mapping
        int abs_x = (int)(smoothed_x * 65535.0f);
        int abs_y = (int)(smoothed_y * 65535.0f);

        INPUT input;
        ZeroMemory(&input, sizeof(input));
        input.type = INPUT_MOUSE;
        input.mi.dx = abs_x;
        input.mi.dy = abs_y;
        // MOUSEEVENTF_VIRTUALDESK handles multi-monitor setups better
        input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
        
        SendInput(1, &input, sizeof(INPUT));
    }

    last_pinch_mask = pinch_mask;
}

int input_injector_execute(action_t action, int dry_run) {
    if (action == ACTION_NONE || dry_run) return 1;
    if (action == ACTION_CLICK_RIGHT) {
        INPUT inputs[2];
        ZeroMemory(inputs, sizeof(inputs));
        inputs[0].type = INPUT_MOUSE;
        inputs[0].mi.dwFlags = MOUSEEVENTF_RIGHTDOWN;
        inputs[1].type = INPUT_MOUSE;
        inputs[1].mi.dwFlags = MOUSEEVENTF_RIGHTUP;
        SendInput(2, inputs, sizeof(INPUT));
        return 1;
    }
    WORD vk = action_to_vk(action);
    if (vk == 0) return 1;
    INPUT inputs[2];
    ZeroMemory(inputs, sizeof(inputs));
    inputs[0].type = INPUT_KEYBOARD; inputs[0].ki.wVk = vk;
    inputs[1].type = INPUT_KEYBOARD; inputs[1].ki.wVk = vk; inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;
    SendInput(2, inputs, sizeof(INPUT));
    return 1;
}

void input_injector_set_key_state(unsigned short vk, int is_down, int dry_run) {
    if (vk == 0 || dry_run) return;
    INPUT input;
    ZeroMemory(&input, sizeof(input));
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = vk;
    input.ki.dwFlags = is_down ? 0 : KEYEVENTF_KEYUP;
    SendInput(1, &input, sizeof(INPUT));
}

void input_injector_type_key(const char* key_name, int dry_run) {
    if (key_name == NULL || *key_name == '\0' || dry_run) return;
    WORD vk = 0;
    if (strlen(key_name) == 1) {
        char c = key_name[0];
        if (c >= 'A' && c <= 'Z') vk = c;
        else if (c >= 'a' && c <= 'z') vk = c - ('a' - 'A');
    } else {
        if (strcmp(key_name, "SPACE") == 0) vk = VK_SPACE;
        else if (strcmp(key_name, "BACKSPACE") == 0) vk = VK_BACK;
        else if (strcmp(key_name, "ENTER") == 0) vk = VK_RETURN;
    }
    if (vk != 0) {
        INPUT inputs[2];
        ZeroMemory(inputs, sizeof(inputs));
        inputs[0].type = INPUT_KEYBOARD; inputs[0].ki.wVk = vk;
        inputs[1].type = INPUT_KEYBOARD; inputs[1].ki.wVk = vk; inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;
        SendInput(2, inputs, sizeof(INPUT));
    }
}
