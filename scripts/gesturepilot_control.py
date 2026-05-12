#!/usr/bin/env python3
"""
GesturePilot Control: Real-time gesture recognition with mouse/keyboard control.
Uses ONNX model with keyboard/mouse automation.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, Dict
from collections import deque

import cv2
import numpy as np
import onnxruntime as rt

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

class GestureController:
    def __init__(self, model_path: str, config_path: Optional[str] = None):
        self.model_path = Path(model_path)
        self.config = self._load_config(config_path)
        self.session = None
        self.input_name = None
        self.output_name = None
        self.gesture_names = ["fist", "point", "v_sign", "three", "four", "open_palm"]
        self.action_map = {}
        self._init_onnx()
        self._load_action_map(config_path)
        
        # Temporal filtering
        self.gesture_history = deque(maxlen=10)
        self.last_action_time = 0
        self.current_stable_gesture = None
    
    def _load_config(self, config_path: Optional[str]) -> dict:
        default_config = {
            "confidence_threshold": 0.80,
            "stable_frames": 4,
            "cooldown_ms": 900,
            "camera_id": 0,
            "display": True,
            "mouse_speed": 5,
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            
                            if value.lower() in ("true", "false"):
                                default_config[key] = value.lower() == "true"
                            elif value.isdigit():
                                default_config[key] = int(value)
                            elif value.replace(".", "", 1).isdigit():
                                default_config[key] = float(value)
        
        return default_config
    
    def _load_action_map(self, config_path: Optional[str]):
        """Load gesture-to-action mapping from config file."""
        if not config_path or not Path(config_path).exists():
            return
        
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("map."):
                    parts = line[4:].split("=", 1)
                    if len(parts) == 2:
                        gesture = parts[0].strip()
                        action = parts[1].strip()
                        self.action_map[gesture] = action
    
    def _init_onnx(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        sess_options = rt.SessionOptions()
        sess_options.log_severity_level = 3
        self.session = rt.InferenceSession(str(self.model_path), sess_options)
        
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Convert frame to model input."""
        frame = cv2.resize(frame, (96, 96))
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_float = frame_rgb.astype(np.float32) / 255.0
        
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        frame_norm = (frame_float - mean) / std
        frame_input = np.transpose(frame_norm, (2, 0, 1))
        
        return np.expand_dims(frame_input, 0)
    
    def predict(self, frame: np.ndarray) -> Tuple[str, float]:
        """Run inference and return gesture name and confidence."""
        frame_input = self.preprocess_frame(frame)
        outputs = self.session.run([self.output_name], {self.input_name: frame_input})
        
        logits = outputs[0][0]
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        gesture_id = int(np.argmax(probs))
        confidence = float(probs[gesture_id])
        gesture_name = self.gesture_names[gesture_id] if gesture_id < len(self.gesture_names) else "unknown"
        
        return gesture_name, confidence
    
    def check_stable_gesture(self, gesture: str, confidence: float) -> Optional[str]:
        """Apply temporal filtering to detect stable gestures."""
        current_time = time.time() * 1000
        
        if confidence >= self.config["confidence_threshold"]:
            self.gesture_history.append(gesture)
        else:
            self.gesture_history.append(None)
        
        if len(self.gesture_history) >= self.config["stable_frames"]:
            last_n = list(self.gesture_history)[-self.config["stable_frames"]:]
            if all(g == last_n[0] and g is not None for g in last_n):
                if current_time - self.last_action_time >= self.config["cooldown_ms"]:
                    self.last_action_time = current_time
                    return last_n[0]
        
        return None
    
    def execute_action(self, gesture: str) -> bool:
        """Execute action based on gesture."""
        if not HAS_PYAUTOGUI:
            print(f"Action for gesture '{gesture}' would be executed (pyautogui not available)")
            return True
        
        action = self.action_map.get(gesture)
        if not action:
            return False
        
        try:
            if action == "mouse_left":
                pyautogui.move(-self.config["mouse_speed"], 0, duration=0.1)
            elif action == "mouse_right":
                pyautogui.move(self.config["mouse_speed"], 0, duration=0.1)
            elif action == "mouse_up":
                pyautogui.move(0, -self.config["mouse_speed"], duration=0.1)
            elif action == "mouse_down":
                pyautogui.move(0, self.config["mouse_speed"], duration=0.1)
            elif action == "mouse_click_left":
                pyautogui.click()
            elif action == "mouse_click_right":
                pyautogui.click(button='right')
            elif action == "mouse_scroll_up":
                pyautogui.scroll(3)
            elif action == "mouse_scroll_down":
                pyautogui.scroll(-3)
            elif action == "key_enter":
                pyautogui.press('enter')
            elif action == "key_esc":
                pyautogui.press('esc')
            elif action == "key_space":
                pyautogui.press('space')
            elif action == "key_tab":
                pyautogui.press('tab')
            else:
                return False
            return True
        except Exception as e:
            print(f"Error executing action: {e}")
            return False
    
    def run(self):
        """Run the gesture controller with camera input."""
        cap = cv2.VideoCapture(self.config["camera_id"])
        if not cap.isOpened():
            print("Failed to open camera")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        print("GesturePilot Controller running...")
        print("Gestures configured:")
        for gesture, action in self.action_map.items():
            print(f"  {gesture} -> {action}")
        print("Press 'q' to exit")
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            gesture, confidence = self.predict(frame)
            
            stable_gesture = self.check_stable_gesture(gesture, confidence)
            if stable_gesture:
                self.execute_action(stable_gesture)
                print(f"[{frame_count}] Executed: {stable_gesture} -> {self.action_map.get(stable_gesture)}")
            
            if self.config["display"]:
                display_frame = cv2.resize(frame, (640, 480))
                cv2.putText(display_frame, f"Gesture: {gesture} ({confidence:.2f})", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                if stable_gesture:
                    cv2.putText(display_frame, f"Action: {self.action_map.get(stable_gesture)}", (10, 70),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                
                cv2.imshow("GesturePilot Control (Q to exit)", display_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        if self.config["display"]:
            cv2.destroyAllWindows()

def main():
    parser = argparse.ArgumentParser(description="GesturePilot Controller")
    parser.add_argument("--model", type=str, default="models/gesturepilot.onnx",
                       help="Path to ONNX model")
    parser.add_argument("--config", type=str, default="config/gesturepilot.sample.ini",
                       help="Path to config file")
    parser.add_argument("--camera", type=int, default=0, help="Camera ID")
    parser.add_argument("--no-display", action="store_true", help="Disable display")
    args = parser.parse_args()
    
    if not HAS_PYAUTOGUI:
        print("WARNING: pyautogui not installed. Install with: pip install pyautogui")
        print("Continuing in demonstration mode...")
    
    try:
        controller = GestureController(args.model, args.config)
        if args.no_display:
            controller.config["display"] = False
        controller.config["camera_id"] = args.camera
        controller.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
