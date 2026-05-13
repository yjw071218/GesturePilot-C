import cv2
import mediapipe as mp
import math
import time
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

def get_dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def is_finger_bent_fast(hand_lms, tip_idx, pip_idx, mcp_idx):
    # Tip-MCP vs PIP-MCP ratio. 
    # Using 0.97 to be VERY sensitive for slight movements.
    d_tip_mcp = get_dist(hand_lms[tip_idx], hand_lms[mcp_idx])
    d_pip_mcp = get_dist(hand_lms[pip_idx], hand_lms[mcp_idx])
    return d_tip_mcp < d_pip_mcp * 0.97

def main():
    mouse = MouseController()
    keyboard = KeyboardController()
    
    mp_hands = mp.solutions.hands
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.4, # Lowered slightly to prevent tracking loss during fast motion
        min_tracking_confidence=0.4,
        model_complexity=0
    )

    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True, 
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened(): return

    # Ensure maximum framerate
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640) 
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    LEFT_IRIS = [474, 475, 476, 477]
    RIGHT_IRIS = [469, 470, 471, 472]

    # States
    rhythm_mode = False
    last_rhythm_toggle_time = 0
    last_left_pinch_pos = None
    left_pinch_threshold = 0.04
    
    is_left_down = False
    is_right_down = False
    active_pinch_type = None
    last_scroll_y = 0

    # Key management: Current real-time state
    key_states = {'w': False, 'd': False, 'k': False, 'p': False}

    def get_gaze_point(face_landmarks):
        lx = (face_landmarks[474].x + face_landmarks[476].x) / 2
        ly = (face_landmarks[474].y + face_landmarks[476].y) / 2
        rx = (face_landmarks[469].x + face_landmarks[471].x) / 2
        ry = (face_landmarks[469].y + face_landmarks[471].y) / 2
        nose = face_landmarks[168]
        dx, dy = ((lx+rx)/2 - nose.x) * 12 + 0.5, ((ly+ry)/2 - nose.y) * 12 + 0.5
        return max(0, min(1, dx)), max(0, min(1, dy))

    def map_to_screen(val, margin=0.25):
        return max(0, min(1, (val - margin) / (1 - 2 * margin)))

    while True:
        success, image = cap.read()
        if not success: continue

        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        hand_results = hands.process(image_rgb)
        face_results = None
        if not rhythm_mode:
            face_results = face_mesh.process(image_rgb)

        gaze_x, gaze_y = 0.5, 0.5
        if face_results and face_results.multi_face_landmarks:
            gaze_x, gaze_y = get_gaze_point(face_results.multi_face_landmarks[0].landmark)

        current_pinch = None
        hand_pos = (0.5, 0.5)
        hand_detected = False
        
        # Reset current frame key detections to False, then update based on landmarks
        # This ensures simultaneous presses are caught in one frame
        detected_keys_this_frame = {'w': False, 'd': False, 'k': False, 'p': False}
        
        if hand_results.multi_hand_landmarks:
            right_idx, left_idx = -1, -1
            for i, handedness in enumerate(hand_results.multi_handedness):
                if handedness.classification[0].label == "Right": right_idx = i
                else: left_idx = i
            
            if right_idx != -1 or left_idx != -1:
                hand_detected = True
            
            # --- Left Hand ---
            if left_idx != -1:
                l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                
                # Mode Toggle
                if get_dist(l_lms[4], l_lms[20]) < 0.05:
                    if time.time() - last_rhythm_toggle_time > 1.0:
                        rhythm_mode = not rhythm_mode
                        last_rhythm_toggle_time = time.time()
                
                # Rhythm Keys (w, d)
                if rhythm_mode:
                    detected_keys_this_frame['w'] = is_finger_bent_fast(l_lms, 12, 10, 9)
                    detected_keys_this_frame['d'] = is_finger_bent_fast(l_lms, 8, 6, 5)
                else:
                    # Vol/Nav
                    if get_dist(l_lms[4], l_lms[8]) < 0.05:
                        curr = (l_lms[4].x+l_lms[8].x)/2, (l_lms[4].y+l_lms[8].y)/2
                        if last_left_pinch_pos:
                            dx, dy = curr[0]-last_left_pinch_pos[0], curr[1]-last_left_pinch_pos[1]
                            if abs(dx) > left_pinch_threshold:
                                with keyboard.pressed(Key.alt):
                                    keyboard.tap(Key.right if dx > 0 else Key.left)
                                last_left_pinch_pos = curr
                            if abs(dy) > left_pinch_threshold:
                                keyboard.tap(Key.media_volume_down if dy > 0 else Key.media_volume_up)
                                last_left_pinch_pos = curr
                        else: last_left_pinch_pos = curr
                    else: last_left_pinch_pos = None

            # --- Right Hand ---
            if right_idx != -1:
                r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                if rhythm_mode:
                    detected_keys_this_frame['k'] = is_finger_bent_fast(r_lms, 8, 6, 5)
                    detected_keys_this_frame['p'] = is_finger_bent_fast(r_lms, 12, 10, 9)
                else:
                    # Normal Actions
                    d_idx, d_mid, d_rng = get_dist(r_lms[4], r_lms[8]), get_dist(r_lms[4], r_lms[12]), get_dist(r_lms[4], r_lms[16])
                    T, R = 0.07, 0.12
                    if active_pinch_type == "L" and d_idx < R: current_pinch = "L"
                    elif active_pinch_type == "S" and d_mid < R: current_pinch = "S"
                    elif active_pinch_type == "R" and d_rng < R: current_pinch = "R"
                    
                    if not current_pinch:
                        if d_rng < T: current_pinch = "R"
                        elif d_mid < T: current_pinch = "S"
                        elif d_idx < T: current_pinch = "L"
                    
                    hand_pos = (r_lms[9].x, r_lms[9].y)
                    if current_pinch == "L": hand_pos = ((r_lms[4].x+r_lms[8].x)/2, (r_lms[4].y+r_lms[8].y)/2)

        # --- KEY STATE SYNC (CRITICAL FOR CHORDS/RAPID TAPS) ---
        if rhythm_mode:
            for k in ['w', 'd', 'k', 'p']:
                is_detected = detected_keys_this_frame[k]
                if is_detected and not key_states[k]:
                    keyboard.press(k)
                    key_states[k] = True
                elif not is_detected and key_states[k]:
                    keyboard.release(k)
                    key_states[k] = False

        # --- Injection & Drawing ---
        if not rhythm_mode:
            if current_pinch == "L":
                if not is_left_down: mouse.press(Button.left); is_left_down = True
            else:
                if is_left_down: mouse.release(Button.left); is_left_down = False

            if current_pinch == "R":
                if not is_right_down: mouse.press(Button.right); is_right_down = True
            else:
                if is_right_down: mouse.release(Button.right); is_right_down = False

            if current_pinch == "S":
                cy = r_lms[12].y
                if last_scroll_y != 0:
                    dy = last_scroll_y - cy
                    if abs(dy) > 0.005:
                        mouse.scroll(0, 1 if dy > 0 else -1)
                        last_scroll_y = cy
                else: last_scroll_y = cy
            else: last_scroll_y = 0

            freeze = (current_pinch in ["R", "S"]) or (current_pinch == "L")
            tx, ty = map_to_screen(hand_pos[0]*0.7 + gaze_x*0.3, 0.25), map_to_screen(hand_pos[1]*0.7 + gaze_y*0.3, 0.25)
            
            p_mask = 0
            if not hand_detected: p_mask |= 16
            elif freeze: p_mask |= 16
            
            gesture_name = "point" if hand_detected else "none"
            print(f"{gesture_name} 1.0 {tx:.4f} {ty:.4f} {p_mask} 0 0", flush=True)

            if hand_results.multi_hand_landmarks:
                for hand_lms in hand_results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(image, hand_lms, mp_hands.HAND_CONNECTIONS,
                                            mp_drawing_styles.get_default_hand_landmarks_style(),
                                            mp_drawing_styles.get_default_hand_connections_style())
        else:
            print(f"none 1.0 0.5 0.5 16 0 0", flush=True)

        active_pinch_type = current_pinch
        ui_text = f"MODE: {'RHYTHM' if rhythm_mode else 'NORMAL'}"
        cv2.putText(image, ui_text, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        if rhythm_mode:
            # Show active keys for feedback
            active_keys_str = " ".join([k.upper() for k, v in key_states.items() if v])
            if active_keys_str:
                cv2.putText(image, f"KEYS: {active_keys_str}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow('GesturePilot', image)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
