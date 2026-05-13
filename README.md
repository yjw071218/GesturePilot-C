# GesturePilot-C

GesturePilot-C is a high-performance, low-latency gesture control system that translates hand movements into mouse and keyboard inputs. It features a hybrid architecture with a Python-based MediaPipe tracker and a C-based input injector for maximum responsiveness.

## ✨ Key Features

- **High Responsiveness**: Optimized C core for minimal input lag.
- **Precision Tracking**: MediaPipe-powered hand tracking with gaze-assisted stability.
- **Productivity Gestures**:
  - **Virtual Desktop Switch**: 4-finger swipe (Left/Right) to switch Windows desktops.
  - **Window Snapping**: Fist swipe (Left/Right) to snap windows to screen edges.
- **Rhythm Game Mode**: Ultra-low latency mode specifically tuned for rhythm games like *A Dance of Fire and Ice*.
- **Intuitive Controls**:
  - Left/Right click via pinching.
  - Scrolling with middle finger pinch.
  - Volume control with left hand vertical movement.
  - Two-handed zoom support.

## 🚀 Getting Started

### Prerequisites
- Windows 10/11
- Webcam
- CMake (for building the C core)
- Python 3.10+

### Installation & Execution
Simply run the included batch file to set up the environment and start the application:
```batch
run_gesture_pilot.bat
```

## 🛠 Configuration

You can fine-tune the behavior in `config/gesturepilot.sample.ini` (rename to `gesturepilot.ini`):
- `confidence_threshold`: Adjust detection sensitivity.
- `stable_frames`: Number of frames to confirm a gesture.
- `model_path`: Path to the ONNX inference model.

## 📜 License
This project is licensed under the MIT License.
