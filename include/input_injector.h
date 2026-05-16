/**
 * @file        input_injector.h
 * @brief       Windows 입력 주입 인터페이스
 * @details     제스처 판정 결과를 마우스와 키보드 입력 이벤트로 변환한다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Company Name. All rights reserved.
 */
#pragma once

#include "gesture_types.h"

// 추상화된 액션을 실제 시스템 입력으로 발생시킴
int input_injector_execute(action_t action, int dry_run);
// 손 좌표와 핀치 상태를 바탕으로 마우스를 갱신함
void input_injector_update_mouse(float x, float y, int pinch_mask, int scroll_delta, int zoom_delta, int dry_run);
// 문자열로 전달된 키 이름을 실제 키보드 입력으로 변환함
void input_injector_type_key(const char* key_name, int dry_run);
// 가상 키 코드의 누름/뗌 상태를 직접 설정함
void input_injector_set_key_state(unsigned short vk, int is_down, int dry_run);

