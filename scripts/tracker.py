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

    # Keyboard setup
    keys = [["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L", ";"],
            ["Z", "X", "C", "V", "B", "N", "M", ",", ".", "/"],
            ["SPACE", "BACKSPACE", "ENTER"]]
    
    class Button():
        def __init__(self, pos, text, size=[40, 40]):
            self.pos = pos
            self.size = size
            self.text = text

    buttonList = []
    for i in range(len(keys)):
        for j, key in enumerate(keys[i]):
            buttonList.append(Button([50 * j + 20, 50 * i + 200], key))

    def drawAll(img, buttonList):
        for button in buttonList:
            x, y = button.pos
            w, h = button.size
            cv2.rectangle(img, button.pos, (x + w, y + h), (255, 0, 255), cv2.FILLED)
            cv2.putText(img, button.text, (x + 10, y + 30),
                        cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 255), 2)
        return img

    last_click_time = 0
    clicked_key = None

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
        
        # Draw keyboard
        image = drawAll(image, buttonList)

        if results.multi_hand_landmarks and results.multi_handedness:
            # Only process first hand
            hand_landmarks = results.multi_hand_landmarks[0]
            handedness = results.multi_handedness[0].classification[0].label
            landmarks = hand_landmarks.landmark
            
            # Draw the hand annotations on the image.
            mp_drawing.draw_landmarks(
                image,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style())

            # Pinch detection (Thumb tip and Index tip)
            thumb_tip = landmarks[mp_hands.HandLandmark.THUMB_TIP]
            index_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            middle_tip = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
            
            # Index pinch for mouse click/drag
            dx = thumb_tip.x - index_tip.x
            dy = thumb_tip.y - index_tip.y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < 0.04:
                is_pinching = 1
                x = (thumb_tip.x + index_tip.x) / 2.0
                y = (thumb_tip.y + index_tip.y) / 2.0
            else:
                x = index_tip.x
                y = index_tip.y

            # Middle finger pinch for Keyboard typing
            dmx = thumb_tip.x - middle_tip.x
            dmy = thumb_tip.y - middle_tip.y
            dist_middle = math.sqrt(dmx*dmx + dmy*dmy)
            
            h, w, c = image.shape
            cursor_x, cursor_y = int(index_tip.x * w), int(index_tip.y * h)

            if dist_middle < 0.04:
                current_time = math.floor(math.get_time() * 1000) if hasattr(math, 'get_time') else int(math.fmod(cv2.getTickCount() / cv2.getTickFrequency() * 1000, 1000000000))
                
                # Check keyboard buttons
                for button in buttonList:
                    bx, by = button.pos
                    bw, bh = button.size
                    if bx < cursor_x < bx + bw and by < cursor_y < by + bh:
                        if clicked_key != button.text:
                            # Use custom gesture for key press
                            gesture = f"KEY_{button.text}"
                            confidence = 0.99
                            clicked_key = button.text
                            # Visual feedback
                            cv2.rectangle(image, button.pos, (bx + bw, by + bh), (0, 255, 0), cv2.FILLED)
                
            else:
                clicked_key = None

            # Determine other gestures only if not pinching
            if not is_pinching and gesture == "GESTURE_NONE":
                fingers_state = []
                # Thumb
                if handedness == "Right":
                    fingers_state.append(thumb_tip.x < landmarks[mp_hands.HandLandmark.THUMB_IP].x)
                else:
                    fingers_state.append(thumb_tip.x > landmarks[mp_hands.HandLandmark.THUMB_IP].x)
                # Others
                for tip_idx, pip_idx in zip(finger_tips, finger_pips):
                    fingers_state.append(landmarks[tip_idx].y < landmarks[pip_idx].y)
                
                fingers_extended = sum(fingers_state)
                
                if fingers_extended == 0:
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
