#include "input_injector.h"

#include <stdio.h>
#include <windows.h>

#define MOUSE_SPEED 5
#define SCREEN_WIDTH 1920
#define SCREEN_HEIGHT 1080

static int g_mouse_x = SCREEN_WIDTH / 2;
static int g_mouse_y = SCREEN_HEIGHT / 2;

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

static void move_mouse_relative(int dx, int dy) {
    POINT pt;
    if (GetCursorPos(&pt)) {
        g_mouse_x = pt.x;
        g_mouse_y = pt.y;
    }
    
    g_mouse_x += dx * MOUSE_SPEED;
    g_mouse_y += dy * MOUSE_SPEED;
    
    if (g_mouse_x < 0) g_mouse_x = 0;
    if (g_mouse_x >= SCREEN_WIDTH) g_mouse_x = SCREEN_WIDTH - 1;
    if (g_mouse_y < 0) g_mouse_y = 0;
    if (g_mouse_y >= SCREEN_HEIGHT) g_mouse_y = SCREEN_HEIGHT - 1;
    
    SetCursorPos(g_mouse_x, g_mouse_y);
}

static void mouse_click(int button) {
    INPUT input;
    ZeroMemory(&input, sizeof(input));
    input.type = INPUT_MOUSE;
    
    if (button == 1) {
        input.mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
        SendInput(1, &input, sizeof(INPUT));
        Sleep(50);
        input.mi.dwFlags = MOUSEEVENTF_LEFTUP;
        SendInput(1, &input, sizeof(INPUT));
    } else if (button == 2) {
        input.mi.dwFlags = MOUSEEVENTF_RIGHTDOWN;
        SendInput(1, &input, sizeof(INPUT));
        Sleep(50);
        input.mi.dwFlags = MOUSEEVENTF_RIGHTUP;
        SendInput(1, &input, sizeof(INPUT));
    }
}

static void mouse_scroll(int delta) {
    INPUT input;
    ZeroMemory(&input, sizeof(input));
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = MOUSEEVENTF_WHEEL;
    input.mi.mouseData = delta * 120;
    SendInput(1, &input, sizeof(INPUT));
}

int input_injector_execute(action_t action, int dry_run) {
    WORD vk = action_to_vk(action);
    
    if (action == ACTION_NONE) {
        return 1;
    }

    if (dry_run) {
        printf("[dry-run] input action=%d skipped\n", action);
        return 1;
    }

    if (vk != 0) {
        return send_key(vk);
    }

    switch (action) {
        case ACTION_MOUSE_LEFT:
            move_mouse_relative(-1, 0);
            return 1;
        case ACTION_MOUSE_RIGHT:
            move_mouse_relative(1, 0);
            return 1;
        case ACTION_MOUSE_UP:
            move_mouse_relative(0, -1);
            return 1;
        case ACTION_MOUSE_DOWN:
            move_mouse_relative(0, 1);
            return 1;
        case ACTION_MOUSE_CLICK_LEFT:
            mouse_click(1);
            return 1;
        case ACTION_MOUSE_CLICK_RIGHT:
            mouse_click(2);
            return 1;
        case ACTION_MOUSE_SCROLL_UP:
            mouse_scroll(3);
            return 1;
        case ACTION_MOUSE_SCROLL_DOWN:
            mouse_scroll(-3);
            return 1;
        case ACTION_KEY_ENTER:
            return send_key(VK_RETURN);
        case ACTION_KEY_ESC:
            return send_key(VK_ESCAPE);
        case ACTION_KEY_SPACE:
            return send_key(VK_SPACE);
        case ACTION_KEY_BACKSPACE:
            return send_key(VK_BACK);
        case ACTION_KEY_DELETE:
            return send_key(VK_DELETE);
        case ACTION_KEY_TAB:
            return send_key(VK_TAB);
        default:
            return 0;
    }
}

