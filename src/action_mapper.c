// 제스처 설정을 실제 실행 액션으로 찾는다.
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

