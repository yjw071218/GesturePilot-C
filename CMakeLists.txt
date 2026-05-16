cmake_minimum_required(VERSION 3.20)
project(GesturePilotC C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_executable(gesturepilot
    src/main.c
    src/config.c
    src/gesture_types.c
    src/action_mapper.c
    src/inference_pipe.c
)

if (WIN32)
    target_sources(gesturepilot PRIVATE src/input_injector_win.c)
    target_compile_definitions(gesturepilot PRIVATE _CRT_SECURE_NO_WARNINGS NOMINMAX)
else ()
    target_sources(gesturepilot PRIVATE src/input_injector_stub.c)
endif ()

target_include_directories(gesturepilot PRIVATE include)

