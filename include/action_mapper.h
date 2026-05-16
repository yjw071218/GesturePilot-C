/**
 * @file        action_mapper.h
 * @brief       제스처를 실행 액션으로 매핑하는 인터페이스
 * @details     설정에 저장된 제스처-액션 바인딩을 실제 실행 액션으로 해석한다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Company Name. All rights reserved.
 */
#pragma once

#include "config.h"

// 설정에 저장된 제스처-액션 연결을 실제 실행할 액션으로 바꿈
action_t action_mapper_resolve(const app_config_t* config, gesture_t gesture);

