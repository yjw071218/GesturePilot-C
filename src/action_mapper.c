/**
 * @file        action_mapper.c
 * @brief       제스처를 실행 액션으로 매핑하는 구현
 * @details     설정에 정의된 제스처-액션 바인딩을 조회해 실제 실행값을 반환한다.
 * @author      유정우 (yjw071218@korea.ac.kr)
 * @version     1.2.0
 * @date        2026-05-17
 * @copyright   Copyright (c) 2026 Company Name. All rights reserved.
 */
#include "action_mapper.h"

action_t action_mapper_resolve(const app_config_t* config, gesture_t gesture) {
    size_t index;
    if (config == NULL) {
        return ACTION_NONE;
    }

    for (index = 0; index < config->binding_count; ++index) {
        if (config->bindings[index].gesture == gesture) {
            return config->bindings[index].action;
        }
    }

    return ACTION_NONE;
}

