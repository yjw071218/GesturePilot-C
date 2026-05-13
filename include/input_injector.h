#pragma once

#include "gesture_types.h"

int input_injector_execute(action_t action, int dry_run);
void input_injector_update_mouse(float x, float y, int is_pinching, int dry_run);

