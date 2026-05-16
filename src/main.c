#include "action_mapper.h"
#include "config.h"
#include "inference.h"
#include "input_injector.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// 플랫폼별 대기 함수를 분기해서 같은 main 루프를 유지함
#ifdef _WIN32
#include <windows.h>
static void sleep_ms(unsigned int ms) { Sleep(ms); }
#else
#include <time.h>
static void sleep_ms(unsigned int ms) {
    struct timespec req = {ms / 1000, (ms % 1000) * 1000000L};
    nanosleep(&req, NULL);
}
#endif

// 프로그램 메인 시작점
int main(int argc, char** argv) {
    app_config_t config;            // 설정 파일과 기본값을 담는 실행 설정
    inference_ctx_t inference_context; // 파이썬 추론 프로세스와 통신하는 컨텍스트
    
    // 설정 파일을 읽기 전에 기본값부터 채워 둠
    config_set_defaults(&config);

    // 파이썬 트래커와 연결할 파이프를 먼저 연다
    if (!inference_init(&inference_context, config.model_path)) {
        fprintf(stderr, "Python tracker init failed.\n");
        return 1;
    }

    // 실행 상태를 콘솔에 간단히 표시함
    printf("GesturePilot-C started\n");
    printf("Mouse logic is processed in python.\n");

    // 추론 결과를 읽어서 입력으로 바꾸는 메인 루프
    while (1) {
        prediction_t prediction = inference_run(&inference_context); // 파이썬이 보낸 한 프레임의 예측 결과
        
        if (prediction.confidence < 0.0f) break;
        
        input_injector_update_mouse(prediction.x, prediction.y, prediction.pinch_mask, 
                                     prediction.scroll_delta, prediction.zoom_delta, 
                                     config.dry_run);

        action_t action = action_mapper_resolve(&config, prediction.gesture); // 제스처를 설정된 시스템 액션으로 변환
        if (action != ACTION_NONE) {
            input_injector_execute(action, config.dry_run);
        }

        if (prediction.gesture == GESTURE_KEY && prediction.key_name[0] != '\0') {
            input_injector_type_key(prediction.key_name, config.dry_run);
        }
        
        sleep_ms(1);
    }

    inference_shutdown(&inference_context);
    return 0;
}
