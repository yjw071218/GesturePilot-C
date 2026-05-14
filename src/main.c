#include "action_mapper.h"
#include "config.h"
#include "inference.h"
#include "input_injector.h"
#include "temporal_filter.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
// Windows 환경에서의 밀리초 단위 대기 함수
static void sleep_ms(unsigned int ms) { Sleep(ms); }
#else
#include <time.h>
// POSIX 환경에서의 밀리초 단위 대기 함수
static void sleep_ms(unsigned int ms) {
    struct timespec req = {ms / 1000, (ms % 1000) * 1000000L};
    nanosleep(&req, NULL);
}
#endif

/**
 * GesturePilot-C 메인 진입점
 * Python 트래커로부터 데이터를 받아 C 인젝터를 통해 입력을 주입하는 루프를 실행함
 */
int main(int argc, char** argv) {
    app_config_t config;
    inference_ctx_t inference_context;
    
    // 기본 설정값 로드
    config_set_defaults(&config);

    // Python 트래커 프로세스 초기화 및 파이프 연결
    if (!inference_init(&inference_context, config.model_path)) {
        fprintf(stderr, "Python 트래커를 초기화하는 데 실패했습니다.\n");
        return 1;
    }

    printf("GesturePilot-C (Python 엔진 모드) 시작됨\n");
    printf("마우스 클릭, 스크롤, 줌 동작은 Python 스크립트에서 직접 처리됩니다.\n");

    // 메인 처리 루프
    while (1) {
        // 파이프를 통해 Python 트래커로부터 예측 결과 수신
        prediction_t prediction = inference_run(&inference_context);
        
        // 신뢰도가 음수이면 종료 신호로 간주
        if (prediction.confidence < 0.0f) break;
        
        // C 측에서는 좌표를 기반으로 부드러운 마우스 이동을 처리함
        // 클릭, 스크롤, 줌 마스크 정보도 함께 전달됨
        input_injector_update_mouse(prediction.x, prediction.y, prediction.pinch_mask, 
                                     prediction.scroll_delta, prediction.zoom_delta, 
                                     config.dry_run);

        // 제스처 타입에 따라 매핑된 액션이 있으면 실행 (미디어 키 등)
        action_t action = action_mapper_resolve(&config, prediction.gesture);
        if (action != ACTION_NONE) {
            input_injector_execute(action, config.dry_run);
        }

        // 특정 키 입력 제스처인 경우 처리
        if (prediction.gesture == GESTURE_KEY && prediction.key_name[0] != '\0') {
            input_injector_type_key(prediction.key_name, config.dry_run);
        }
        
        // 파이프 대기 중 CPU 점유율 과다 사용을 방지하기 위한 짧은 대기
        sleep_ms(1);
    }

    // 자원 해제 및 Python 트래커 종료
    inference_shutdown(&inference_context);
    return 0;
}
