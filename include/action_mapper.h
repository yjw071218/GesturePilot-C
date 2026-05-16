// 제스처 설정을 실제 실행 액션으로 연결하는 매핑 인터페이스다.
#pragma once

#include "config.h"

// 설정에 저장된 제스처-액션 연결을 실제 실행할 액션으로 바꿈
action_t action_mapper_resolve(const app_config_t* config, gesture_t gesture);

