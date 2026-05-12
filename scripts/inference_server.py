#!/usr/bin/env python3
"""
Gesture inference server: reads frames from stdin, outputs predictions to stdout.
"""

import json
import sys
import numpy as np
from pathlib import Path
import onnxruntime as rt

def setup_inference(model_path: str):
    model_path = Path(model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    sess_options = rt.SessionOptions()
    sess_options.log_severity_level = 3
    session = rt.InferenceSession(str(model_path), sess_options)
    
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    
    return session, input_name, output_name

def predict(session, input_name, output_name, frame_data):
    """
    frame_data: flattened 96x96x3 image as list of floats [0, 1]
    Returns: gesture_id and confidence
    """
    frame_array = np.array(frame_data, dtype=np.float32).reshape(1, 3, 96, 96)
    
    outputs = session.run(
        [output_name],
        {input_name: frame_array}
    )
    logits = outputs[0][0]
    confidences = np.exp(logits) / np.sum(np.exp(logits))
    gesture_id = int(np.argmax(confidences))
    confidence = float(confidences[gesture_id])
    
    return gesture_id, confidence

def main():
    if len(sys.argv) < 2:
        print("Usage: inference_server.py <model_path>", file=sys.stderr)
        sys.exit(1)
    
    model_path = sys.argv[1]
    try:
        session, input_name, output_name = setup_inference(model_path)
    except Exception as e:
        print(f"Failed to load model: {e}", file=sys.stderr)
        sys.exit(1)
    
    print("READY", flush=True)
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            data = json.loads(line.strip())
            if "frame" not in data:
                continue
            
            frame_data = data["frame"]
            gesture_id, confidence = predict(session, input_name, output_name, frame_data)
            
            result = {
                "gesture": gesture_id,
                "confidence": confidence
            }
            print(json.dumps(result), flush=True)
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)

if __name__ == "__main__":
    main()
