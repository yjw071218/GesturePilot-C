#include "input_injector.h"

#include <stdio.h>
#include <windows.h>

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

static int send_key(WORD vk) {
    INPUT inputs[2];
    UINT sent;

    ZeroMemory(inputs, sizeof(inputs));
    inputs[0].type = INPUT_KEYBOARD;
    inputs[0].ki.wVk = vk;

    inputs[1].type = INPUT_KEYBOARD;
    inputs[1].ki.wVk = vk;
    inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;

    sent = SendInput(2, inputs, sizeof(INPUT));
    return sent == 2 ? 1 : 0;
}

int input_injector_execute(action_t action, int dry_run) {
    if (action == ACTION_NONE) {
        return 1;
    }

    if (dry_run) {
        printf("[dry-run] input action=%d skipped\n", action);
        return 1;
    }

    if (action == ACTION_CLICK_RIGHT) {
        INPUT inputs[2];
        ZeroMemory(inputs, sizeof(inputs));
        inputs[0].type = INPUT_MOUSE;
        inputs[0].mi.dwFlags = MOUSEEVENTF_RIGHTDOWN;
        inputs[1].type = INPUT_MOUSE;
        inputs[1].mi.dwFlags = MOUSEEVENTF_RIGHTUP;
        return SendInput(2, inputs, sizeof(INPUT)) == 2 ? 1 : 0;
    }

    WORD vk = action_to_vk(action);
    if (vk == 0) {
        return 1;
    }

    return send_key(vk);
}

static int last_is_pinching = 0;
static float smoothed_x = 0.5f;
static float smoothed_y = 0.5f;

void input_injector_update_mouse(float x, float y, int is_pinching, int dry_run) {
    if (dry_run) {
        return;
    }

    // Exponential moving average for smoothing
    // Use lower alpha (more smoothing) when pinching to prevent cursor jitter during clicks
    float alpha = is_pinching ? 0.05f : 0.5f; 
    
    smoothed_x = smoothed_x * (1.0f - alpha) + x * alpha;
    smoothed_y = smoothed_y * (1.0f - alpha) + y * alpha;

    int abs_x = (int)(smoothed_x * 65535.0f);
    int abs_y = (int)(smoothed_y * 65535.0f);

    INPUT inputs[3];
    ZeroMemory(inputs, sizeof(inputs));
    int input_count = 0;

    // Always move mouse
    inputs[input_count].type = INPUT_MOUSE;
    inputs[input_count].mi.dx = abs_x;
    inputs[input_count].mi.dy = abs_y;
    inputs[input_count].mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE;
    input_count++;

    if (is_pinching && !last_is_pinching) {
        inputs[input_count].type = INPUT_MOUSE;
        inputs[input_count].mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
        input_count++;
    } else if (!is_pinching && last_is_pinching) {
        inputs[input_count].type = INPUT_MOUSE;
        inputs[input_count].mi.dwFlags = MOUSEEVENTF_LEFTUP;
        input_count++;
    }

    last_is_pinching = is_pinching;
    SendInput(input_count, inputs, sizeof(INPUT));
}

void input_injector_type_key(const char* key_name, int dry_run) {
    if (key_name == NULL || *key_name == '\0' || dry_run) {
        return;
    }

    WORD vk = 0;
    if (strlen(key_name) == 1) {
        char c = key_name[0];
        if (c >= 'A' && c <= 'Z') vk = c;
        else if (c >= 'a' && c <= 'z') vk = c - ('a' - 'A');
        else if (c == ';') vk = VK_OEM_1;
        else if (c == ',') vk = VK_OEM_COMMA;
        else if (c == '.') vk = VK_OEM_PERIOD;
        else if (c == '/') vk = VK_OEM_2;
    } else {
        if (strcmp(key_name, "SPACE") == 0) vk = VK_SPACE;
        else if (strcmp(key_name, "BACKSPACE") == 0) vk = VK_BACK;
        else if (strcmp(key_name, "ENTER") == 0) vk = VK_RETURN;
    }

    if (vk != 0) {
        send_key(vk);
    }
}

