#!/usr/bin/env python3
"""
GesturePilot Main Application: Real-time gesture recognition and PC control.
Uses camera input with OpenCV and ONNX Runtime for inference.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import onnxruntime as rt

class GesturePilotApp:
    def __init__(self, model_path: str, config_path: Optional[str] = None):
        self.model_path = Path(model_path)
        self.config = self._load_config(config_path)
        self.session = None
        self.input_name = None
        self.output_name = None
        self.gesture_names = ["fist", "point", "v_sign", "three", "four", "open_palm"]
        self._init_onnx()
    
    def _load_config(self, config_path: Optional[str]) -> dict:
        default_config = {
            "confidence_threshold": 0.80,
            "stable_frames": 4,
            "cooldown_ms": 900,
            "loop_interval_ms": 33,
            "camera_id": 0,
            "display": True,
            "dry_run": False
        }
        
        if config_path and Path(config_path).exists():
            config = {}
            with open(config_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            
                            if value.lower() in ("true", "false"):
                                config[key] = value.lower() == "true"
                            elif value.isdigit():
                                config[key] = int(value)
                            elif value.replace(".", "", 1).isdigit():
                                config[key] = float(value)
                            else:
                                config[key] = value
            
            default_config.update(config)
        
        return default_config
    
    def _init_onnx(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        sess_options = rt.SessionOptions()
        sess_options.log_severity_level = 3
        self.session = rt.InferenceSession(str(self.model_path), sess_options)
        
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Convert frame to model input format."""
        if frame.shape[0] > 0 and frame.shape[1] > 0:
            frame = cv2.resize(frame, (96, 96))
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_float = frame_rgb.astype(np.float32) / 255.0
        
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        
        frame_normalized = (frame_float - mean) / std
        frame_input = np.transpose(frame_normalized, (2, 0, 1))
        frame_batch = np.expand_dims(frame_input, 0)
        
        return frame_batch
    
    def predict(self, frame: np.ndarray) -> Tuple[int, float]:
        """Run inference on frame."""
        frame_input = self.preprocess_frame(frame)
        
        outputs = self.session.run([self.output_name], {self.input_name: frame_input})
        logits = outputs[0][0]
        
        exp_logits = np.exp(logits - np.max(logits))
        probabilities = exp_logits / np.sum(exp_logits)
        
        gesture_id = int(np.argmax(probabilities))
        confidence = float(probabilities[gesture_id])
        
        return gesture_id, confidence
    
    def run_camera(self):
        """Run real-time gesture recognition from camera."""
        cap = cv2.VideoCapture(self.config["camera_id"])
        
        if not cap.isOpened():
            print("Failed to open camera")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        frame_count = 0
        gesture_history = []
        
        print("Starting gesture recognition (press 'q' to exit)...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            gesture_id, confidence = self.predict(frame)
            
            if confidence >= self.config["confidence_threshold"]:
                gesture_name = self.gesture_names[gesture_id] if gesture_id < len(self.gesture_names) else "unknown"
                gesture_history.append((gesture_name, confidence))
            
            if self.config["display"]:
                display_frame = cv2.resize(frame, (640, 480))
                
                gesture_name = self.gesture_names[gesture_id] if gesture_id < len(self.gesture_names) else "unknown"
                cv2.putText(display_frame, f"Gesture: {gesture_name}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(display_frame, f"Confidence: {confidence:.2f}", (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(display_frame, f"Frame: {frame_count}", (10, 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                cv2.imshow("GesturePilot - Press Q to exit", display_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        if self.config["display"]:
            cv2.destroyAllWindows()
        
        print(f"Total frames: {frame_count}")
        if gesture_history:
            print(f"Unique gestures detected: {len(set([g[0] for g in gesture_history]))}")

def main():
    parser = argparse.ArgumentParser(description="GesturePilot - Real-time Gesture Recognition")
    parser.add_argument("--model", type=str, default="models/gesturepilot.onnx",
                       help="Path to ONNX model")
    parser.add_argument("--config", type=str, default="config/gesturepilot.sample.ini",
                       help="Path to config file")
    parser.add_argument("--camera", type=int, default=0, help="Camera device ID")
    parser.add_argument("--display", action="store_true", default=True,
                       help="Display video feed with predictions")
    parser.add_argument("--no-display", action="store_true", help="Disable display")
    args = parser.parse_args()
    
    try:
        app = GesturePilotApp(args.model, args.config)
        if args.no_display:
            app.config["display"] = False
        else:
            app.config["display"] = args.display
        app.config["camera_id"] = args.camera
        
        app.run_camera()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
