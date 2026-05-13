#pragma once

#include "gesture_types.h"

int input_injector_execute(action_t action, int dry_run);
void input_injector_update_mouse(float x, float y, int pinch_mask, int scroll_delta, int zoom_delta, int dry_run);
void input_injector_type_key(const char* key_name, int dry_run);
void input_injector_set_key_state(unsigned short vk, int is_down, int dry_run);

