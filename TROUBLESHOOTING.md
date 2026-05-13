# Troubleshooting Guide

If you encounter issues with GesturePilot-C, check this guide for common solutions.

## ⚠️ Common Issues

### 1. Cursor Jitter or Jumping
- **Lighting**: Ensure your hand is well-lit. Avoid strong backlighting (like a window behind you).
- **Background**: A complex or moving background can confuse the tracker. Try a plain background.
- **Distance**: Keep your hand between 0.5m and 1.5m from the camera.

### 2. Gestures Not Registering
- **Hand Visibility**: Ensure your entire hand is within the camera's field of view.
- **Speed**: If you move too fast, MediaPipe may lose track. Try smoother movements.
- **Calibration**: If finger bends aren't detected, check the `bend ratio` in `scripts/tracker.py`.

### 3. High CPU Usage
- The system is optimized, but MediaPipe is a heavy AI model.
- Close other camera-intensive apps.
- Reduce your webcam's resolution in `scripts/tracker.py` if necessary.

### 4. Build Errors
- Ensure you have the **Visual Studio Build Tools** (C++ Desktop Development) installed.
- Check that CMake is added to your system PATH.

## 💬 Getting Support
If you find a bug, please open an issue on the GitHub repository.
