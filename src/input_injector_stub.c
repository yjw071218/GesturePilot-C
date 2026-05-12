#include "input_injector.h"

#include <stdio.h>

int input_injector_execute(action_t action, int dry_run) {
    (void)dry_run;
    printf("[stub] input action=%d\n", action);
    return 1;
}

