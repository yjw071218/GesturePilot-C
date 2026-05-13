# Project Architecture

GesturePilot-C employs a **Hybrid Multi-Process Architecture** to balance the ease of high-level computer vision in Python with the low-latency input execution of C.

## 🏗 System Overview

The system consists of two primary components communicating via standard I/O pipes:

1.  **The Tracker (Python + MediaPipe)**:
    - Captures video frames from the webcam.
    - Uses MediaPipe to extract 21 hand landmarks and 478 face landmarks.
    - Processes high-level gesture logic (swipes, pinches, mode toggles).
    - Maps 3D hand coordinates to 2D screen coordinates using gaze assistance.
    - Sends raw command strings to the Injector via `stdout`.

2.  **The Injector (C + Windows API)**:
    - Receives command strings via `stdin`.
    - Implements **Exponential Moving Average (EMA) Smoothing** to filter jitter.
    - Executes hardware-level mouse and keyboard events using the `SendInput` Windows API.
    - Ensures minimal overhead and zero-lag execution.

## 🔄 Data Flow

```
[Webcam] -> (OpenCV) -> [Python Tracker] -> (Pipe) -> [C Injector] -> (WinAPI) -> [OS Input]
```

## 🚀 Performance Optimizations

- **C-Side Smoothing**: Performing smoothing at the injection layer ensures that the cursor moves at the monitor's refresh rate, even if the tracking frame rate varies.
- **Gaze-Assisted Mapping**: Combines hand position (70%) with eye gaze (30%) to reduce the physical reach required to hit screen corners.
- **Velocity Detection**: Rhythm mode uses finger bending velocity to trigger keys instantly, bypassing traditional threshold lag.
