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
    WORD vk = action_to_vk(action);
    if (action == ACTION_NONE || vk == 0) {
        return 1;
    }

    if (dry_run) {
        printf("[dry-run] input action=%d skipped\n", action);
        return 1;
    }

    return send_key(vk);
}

