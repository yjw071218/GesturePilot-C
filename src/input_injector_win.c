// Windows API로 마우스와 키보드 입력을 주입한다.
#include "input_injector.h"

#include <stdio.h>
#include <windows.h>
#include <math.h>

/**
 * 액션 타입을 Windows 가상 키 코드(VK)로 변환하는 정적 함수
 */
static WORD action_to_vk(action_t action) {
    switch (action) {
        case ACTION_PLAY_PAUSE: return VK_MEDIA_PLAY_PAUSE; // 재생/일시정지
        case ACTION_NEXT_SLIDE: return VK_RIGHT;           // 다음 슬라이드 (오른쪽 화살표)
        case ACTION_PREV_SLIDE: return VK_LEFT;            // 이전 슬라이드 (왼쪽 화살표)
        case ACTION_VOLUME_UP: return VK_VOLUME_UP;        // 볼륨 업
        case ACTION_VOLUME_DOWN: return VK_VOLUME_DOWN;    // 볼륨 다운
        default: return 0;
    }
}

// 상태 유지를 위한 정적 변수들
static float smoothed_x = 0.5f; // EMA 필터링된 X 좌표
static float smoothed_y = 0.5f; // EMA 필터링된 Y 좌표

/**
 * 마우스 위치 업데이트 및 이동 실행 (C 측에서는 부드러운 이동 처리에 집중)
 */
void input_injector_update_mouse(float x, float y, int pinch_mask, int scroll_delta, int zoom_delta, int dry_run) {
    if (dry_run) return;

    // pinch_mask 비트 0: 왼쪽 버튼 눌림 여부
    // pinch_mask 비트 4: Python 측에서 보낸 고정(Freeze) 신호
    int left_now = pinch_mask & 1;
    int freeze_raw = (pinch_mask >> 4) & 1;

    // 움직임 계산 여부 (고정 신호가 없으면 이동)
    int should_move = !freeze_raw;
    
    // 적응형 스무딩 (Adaptive Smoothing):
    // 정밀한 작업이 필요한 경우(클릭/드래그/고정) alpha 값을 낮춰 더 부드럽게(느리게) 이동
    float target_alpha = 0.25f; // 기본 반응성 위주의 값
    
    if (left_now) {
        target_alpha = 0.03f; // 드래그/클릭 시 정밀 고정을 위해 매우 부드럽게
    } else if (freeze_raw) {
        target_alpha = 0.01f; // 우클릭/스크롤 시 커서 튐 방지를 위한 강력한 고정
    }

    // 지수 이동 평균(EMA) 필터를 통한 커서 떨림 방지
    smoothed_x = smoothed_x * (1.0f - target_alpha) + x * target_alpha;
    smoothed_y = smoothed_y * (1.0f - target_alpha) + y * target_alpha;

    if (should_move) {
        // 0.0~1.0 좌표를 Windows 절대 좌표 시스템(0~65535)으로 변환
        int abs_x = (int)(smoothed_x * 65535.0f);
        int abs_y = (int)(smoothed_y * 65535.0f);

        INPUT input;
        ZeroMemory(&input, sizeof(input));
        input.type = INPUT_MOUSE;
        input.mi.dx = abs_x;
        input.mi.dy = abs_y;
        // MOUSEEVENTF_VIRTUALDESK는 멀티 모니터 환경에서 더 정확하게 작동함
        input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
        
        SendInput(1, &input, sizeof(INPUT));
    }
}

/**
 * 정의된 액션(미디어 키 등) 실행
 */
int input_injector_execute(action_t action, int dry_run) {
    if (action == ACTION_NONE || dry_run) return 1;
    
    // 오른쪽 클릭 처리
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

    // 기타 키보드 액션 처리
    WORD vk = action_to_vk(action);
    if (vk == 0) return 1;
    INPUT inputs[2];
    ZeroMemory(inputs, sizeof(inputs));
    inputs[0].type = INPUT_KEYBOARD; inputs[0].ki.wVk = vk;
    inputs[1].type = INPUT_KEYBOARD; inputs[1].ki.wVk = vk; inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;
    SendInput(2, inputs, sizeof(INPUT));
    return 1;
}

/**
 * 특정 가상 키의 상태를 직접 설정 (누름/뗌)
 */
void input_injector_set_key_state(unsigned short vk, int is_down, int dry_run) {
    if (vk == 0 || dry_run) return;
    INPUT input;
    ZeroMemory(&input, sizeof(input));
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = vk;
    input.ki.dwFlags = is_down ? 0 : KEYEVENTF_KEYUP;
    SendInput(1, &input, sizeof(INPUT));
}

/**
 * 키 이름을 기반으로 한 번 탭(누르고 떼기) 실행
 */
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
