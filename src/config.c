#include "config.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char* trim(char* text) {
    char* end;
    while (*text != '\0' && isspace((unsigned char)*text)) {
        text++;
    }

    if (*text == '\0') {
        return text;
    }

    end = text + strlen(text) - 1;
    while (end > text && isspace((unsigned char)*end)) {
        *end = '\0';
        end--;
    }
    return text;
}

void config_set_defaults(app_config_t* out_config) {
    if (out_config == NULL) {
        return;
    }

    memset(out_config, 0, sizeof(*out_config));
    out_config->confidence_threshold = 0.80f;
    out_config->stable_frames = 4;
    out_config->cooldown_ms = 900;
    out_config->loop_interval_ms = 33;
    out_config->total_frames = 600;
    out_config->dry_run = 1;
    strncpy(out_config->model_path, "models\\gesturepilot.onnx", GP_MAX_PATH - 1);

    out_config->bindings[0].gesture = GESTURE_OPEN_PALM;
    out_config->bindings[0].action = ACTION_PLAY_PAUSE;
    out_config->bindings[1].gesture = GESTURE_POINT;
    out_config->bindings[1].action = ACTION_NEXT_SLIDE;
    out_config->bindings[2].gesture = GESTURE_V_SIGN;
    out_config->bindings[2].action = ACTION_PREV_SLIDE;
    out_config->bindings[3].gesture = GESTURE_THREE;
    out_config->bindings[3].action = ACTION_VOLUME_UP;
    out_config->bindings[4].gesture = GESTURE_FOUR;
    out_config->bindings[4].action = ACTION_VOLUME_DOWN;
    out_config->binding_count = 5;
}

static int parse_int(const char* text, int* out_value) {
    char* end_ptr = NULL;
    long value;

    value = strtol(text, &end_ptr, 10);
    if (end_ptr == text || *end_ptr != '\0') {
        return 0;
    }

    *out_value = (int)value;
    return 1;
}

static int parse_float(const char* text, float* out_value) {
    char* end_ptr = NULL;
    float value;

    value = (float)strtod(text, &end_ptr);
    if (end_ptr == text || *end_ptr != '\0') {
        return 0;
    }

    *out_value = value;
    return 1;
}

static int set_mapping(app_config_t* config, const char* key, const char* value) {
    gesture_t gesture;
    action_t action;
    size_t index;

    if (strncmp(key, "map.", 4) != 0) {
        return 0;
    }

    gesture = gesture_from_string(key + 4);
    action = action_from_string(value);
    if (gesture == GESTURE_UNKNOWN) {
        return 0;
    }

    for (index = 0; index < config->binding_count; ++index) {
        if (config->bindings[index].gesture == gesture) {
            config->bindings[index].action = action;
            return 1;
        }
    }

    if (config->binding_count >= GP_MAX_BINDINGS) {
        return 0;
    }

    config->bindings[config->binding_count].gesture = gesture;
    config->bindings[config->binding_count].action = action;
    config->binding_count++;
    return 1;
}

static int write_error(char* buffer, size_t size, const char* text) {
    if (buffer != NULL && size > 0) {
        strncpy(buffer, text, size - 1);
        buffer[size - 1] = '\0';
    }
    return 0;
}

int config_load(const char* path, app_config_t* out_config, char* error_buffer, size_t error_buffer_size) {
    FILE* file;
    char line[512];
    int line_number = 0;

    if (path == NULL || out_config == NULL) {
        return write_error(error_buffer, error_buffer_size, "config path is invalid");
    }

    file = fopen(path, "r");
    if (file == NULL) {
        return write_error(error_buffer, error_buffer_size, "failed to open config file");
    }

    while (fgets(line, (int)sizeof(line), file) != NULL) {
        char* equals;
        char* key;
        char* value;
        line_number++;

        key = trim(line);
        if (*key == '\0' || *key == '#' || *key == ';') {
            continue;
        }

        equals = strchr(key, '=');
        if (equals == NULL) {
            fclose(file);
            return write_error(error_buffer, error_buffer_size, "invalid config line (expected key=value)");
        }

        *equals = '\0';
        value = trim(equals + 1);
        key = trim(key);

        if (strcmp(key, "confidence_threshold") == 0) {
            if (!parse_float(value, &out_config->confidence_threshold)) {
                fclose(file);
                return write_error(error_buffer, error_buffer_size, "invalid confidence_threshold");
            }
        } else if (strcmp(key, "stable_frames") == 0) {
            if (!parse_int(value, &out_config->stable_frames)) {
                fclose(file);
                return write_error(error_buffer, error_buffer_size, "invalid stable_frames");
            }
        } else if (strcmp(key, "cooldown_ms") == 0) {
            if (!parse_int(value, &out_config->cooldown_ms)) {
                fclose(file);
                return write_error(error_buffer, error_buffer_size, "invalid cooldown_ms");
            }
        } else if (strcmp(key, "loop_interval_ms") == 0) {
            if (!parse_int(value, &out_config->loop_interval_ms)) {
                fclose(file);
                return write_error(error_buffer, error_buffer_size, "invalid loop_interval_ms");
            }
        } else if (strcmp(key, "total_frames") == 0) {
            if (!parse_int(value, &out_config->total_frames)) {
                fclose(file);
                return write_error(error_buffer, error_buffer_size, "invalid total_frames");
            }
        } else if (strcmp(key, "dry_run") == 0) {
            if (!parse_int(value, &out_config->dry_run)) {
                fclose(file);
                return write_error(error_buffer, error_buffer_size, "invalid dry_run");
            }
        } else if (strcmp(key, "model_path") == 0) {
            strncpy(out_config->model_path, value, GP_MAX_PATH - 1);
            out_config->model_path[GP_MAX_PATH - 1] = '\0';
        } else if (!set_mapping(out_config, key, value)) {
            fclose(file);
            return write_error(error_buffer, error_buffer_size, "invalid config key/value");
        }
    }

    fclose(file);
    return 1;
}

