#include "input_injector.h"

#include <stdio.h>

int input_injector_execute(action_t action, int dry_run) {
    (void)dry_run;
    printf("[stub] input action=%d\n", action);
    return 1;
}

void input_injector_update_mouse(float x, float y, int is_pinching, int dry_run) {
    (void)dry_run;
    // Stub implementation does nothing
}

