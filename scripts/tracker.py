import cv2
import mediapipe as mp
import math
import sys

def main():
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5, # Reduced for faster detection
        min_tracking_confidence=0.5,    # Reduced for faster tracking
        model_complexity=0 # Use simplest model for lowest latency
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("GESTURE_NONE 0.0 0.5 0.5 0", flush=True)
        return

    # Optimize camera for lower latency
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320) # Lower resolution for faster processing
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Minimize camera buffer


    finger_tips = [
        mp_hands.HandLandmark.INDEX_FINGER_TIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
        mp_hands.HandLandmark.RING_FINGER_TIP,
        mp_hands.HandLandmark.PINKY_TIP
    ]
    finger_pips = [
        mp_hands.HandLandmark.INDEX_FINGER_PIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
        mp_hands.HandLandmark.RING_FINGER_PIP,
        mp_hands.HandLandmark.PINKY_PIP
    ]

    while True:
        success, image = cap.read()
        if not success:
            continue

        # Flip image horizontally for natural mirroring
        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)

        gesture = "GESTURE_NONE"
        confidence = 0.0
        x, y = 0.5, 0.5
        is_pinching = 0

        if results.multi_hand_landmarks and results.multi_handedness:
            # Only process first hand
            hand_landmarks = results.multi_hand_landmarks[0]
            handedness = results.multi_handedness[0].classification[0].label # 'Left' or 'Right'
            
            # Draw the hand annotations on the image.
            mp_drawing.draw_landmarks(
                image,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style())

            landmarks = hand_landmarks.landmark
            
            # Check fingers extended
            # 0: thumb, 1: index, 2: middle, 3: ring, 4: pinky
            fingers_state = []
            
            # Thumb: check if tip is beyond IP joint (horizontal comparison depends on handedness)
            thumb_tip = landmarks[mp_hands.HandLandmark.THUMB_TIP]
            thumb_ip = landmarks[mp_hands.HandLandmark.THUMB_IP]
            thumb_mcp = landmarks[mp_hands.HandLandmark.THUMB_MCP]
            
            if handedness == "Right":
                fingers_state.append(thumb_tip.x < thumb_ip.x)
            else:
                fingers_state.append(thumb_tip.x > thumb_ip.x)
                
            # Other fingers: check if tip is above PIP joint
            for tip_idx, pip_idx in zip(finger_tips, finger_pips):
                fingers_state.append(landmarks[tip_idx].y < landmarks[pip_idx].y)
            
            fingers_extended = sum(fingers_state)

            # Pinch detection (Thumb tip and Index tip)
            index_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            dx = thumb_tip.x - index_tip.x
            dy = thumb_tip.y - index_tip.y
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Threshold for pinch can be adjusted
            if distance < 0.04:
                is_pinching = 1
                # Midpoint for smoother control during pinch
                x = (thumb_tip.x + index_tip.x) / 2.0
                y = (thumb_tip.y + index_tip.y) / 2.0
            else:
                # Use index finger tip for mouse movement when not pinching
                x = index_tip.x
                y = index_tip.y

            # Determine gesture
            if is_pinching:
                gesture = "GESTURE_NONE" # Pinching is handled separately for mouse buttons
                confidence = 0.99
            elif fingers_extended == 0:
                gesture = "GESTURE_FIST"
                confidence = 0.95
            elif fingers_extended == 1 and fingers_state[1]:
                gesture = "GESTURE_POINT"
                confidence = 0.95
            elif fingers_extended == 2 and fingers_state[1] and fingers_state[2]:
                gesture = "GESTURE_V_SIGN"
                confidence = 0.95
            elif fingers_extended >= 4:
                gesture = "GESTURE_OPEN_PALM"
                confidence = 0.95
            else:
                gesture = "GESTURE_UNKNOWN"
                confidence = 0.5


        # Send data to C program
        try:
            print(f"{gesture} {confidence:.2f} {x:.4f} {y:.4f} {is_pinching}", flush=True)
        except OSError:
            # The C program closed the pipe, so we should exit gracefully
            break

        # Show the camera overlay window
        cv2.imshow('GesturePilot Camera Overlay', image)
        
        # Press 'q' to quit, also processes GUI events needed for cv2.imshow
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
