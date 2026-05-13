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
static void sleep_ms(unsigned int ms) { Sleep(ms); }
#else
#include <time.h>
static void sleep_ms(unsigned int ms) {
    struct timespec req = {ms / 1000, (ms % 1000) * 1000000L};
    nanosleep(&req, NULL);
}
#endif

int main(int argc, char** argv) {
    app_config_t config;
    inference_ctx_t inference_context;
    config_set_defaults(&config);

    if (!inference_init(&inference_context, config.model_path)) {
        fprintf(stderr, "Failed to initialize python tracker.\n");
        return 1;
    }

    printf("GesturePilot-C (Python Engine Mode) started\n");
    printf("The python script is now handling mouse actions directly.\n");

    while (1) {
        prediction_t prediction = inference_run(&inference_context);
        if (prediction.confidence < 0.0f) break;
        
        // C side handles movement based on coordinates from Python tracker.
        // Python handles clicks, scrolls, and zoom directly.
        input_injector_update_mouse(prediction.x, prediction.y, prediction.pinch_mask, 
                                     prediction.scroll_delta, prediction.zoom_delta, 
                                     config.dry_run);

        // Also handle other mapped actions if any (though Python is primary now)
        action_t action = action_mapper_resolve(&config, prediction.gesture);
        if (action != ACTION_NONE) {
            input_injector_execute(action, config.dry_run);
        }

        if (prediction.gesture == GESTURE_KEY && prediction.key_name[0] != '\0') {
            input_injector_type_key(prediction.key_name, config.dry_run);
        }
        
        // Small sleep to prevent 100% CPU usage while waiting for pipe
        sleep_ms(1);
    }

    inference_shutdown(&inference_context);
    return 0;
}
