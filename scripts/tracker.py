import cv2
import mediapipe as mp
import math
import time
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

def get_dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def is_finger_extended(hand_lms, tip_idx, pip_idx):
    # Determine if finger is straight based on tip-to-wrist vs pip-to-wrist distance
    return get_dist(hand_lms[tip_idx], hand_lms[0]) > get_dist(hand_lms[pip_idx], hand_lms[0])

def is_finger_bent_fast(hand_lms, tip_idx, pip_idx, mcp_idx):
    # Tip-MCP vs PIP-MCP ratio. 
    # Using 0.99 to be EXTREMELY sensitive for slight movements as requested.
    d_tip_mcp = get_dist(hand_lms[tip_idx], hand_lms[mcp_idx])
    d_pip_mcp = get_dist(hand_lms[pip_idx], hand_lms[mcp_idx])
    return d_tip_mcp < d_pip_mcp * 0.99

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
        min_detection_confidence=0.4, 
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
    rhythm_toggle_start_time = 0 # To prevent accidental toggles
    last_left_pinch_pos = None
    left_pinch_threshold = 0.04
    
    is_left_down = False
    is_right_down = False
    active_pinch_type = None
    last_scroll_y = 0
    
    # Zoom support
    last_two_hand_zoom_dist = 0
    ZOOM_SENSITIVITY = 0.05 # Adjusted for hand-to-hand distance
    
    # Double-click support for Normal Mode
    last_left_click_release_time = 0
    pending_double_click = False
    DOUBLE_CLICK_THRESHOLD = 0.25 # Reverted to original

    # Productivity Swipe state
    last_swipe_time = 0
    wrist_x_history = []
    SWIPE_THRESHOLD = 0.15 # Horizontal movement required
    SWIPE_COOLDOWN = 0.8   # seconds

    # Key management: Current real-time state
    key_states = {'w': False, 'd': False, 'k': False, 'p': False}
    # Track the last time a key was pressed or released to ensure minimum hold/release time
    last_key_press_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
    last_key_release_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
    
    # Velocity-based detection for rhythm keys (to catch rapid flicks)
    last_finger_ratios = {'w': 1.0, 'd': 1.0, 'k': 1.0, 'p': 1.0}
    
    # Hold tolerance: allow a bit more movement once a key is already down
    HOLD_SENSITIVITY_MULTIPLIER = 1.40 # Increased from 1.20 for much stronger lock-on during hold
    
    # Ultra-low latency minimums for rhythm mode
    MIN_KEY_HOLD_TIME = 0.050 # Increased from 0.015 to prevent accidental release/flickering
    MIN_KEY_RELEASE_TIME = 0.015

    def get_gaze_point(face_landmarks):
        lx = (face_landmarks[474].x + face_landmarks[476].x) / 2
        ly = (face_landmarks[474].y + face_landmarks[476].y) / 2
        rx = (face_landmarks[469].x + face_landmarks[471].x) / 2
        ry = (face_landmarks[469].y + face_landmarks[471].y) / 2
        nose = face_landmarks[168]
        # Slightly reduce gaze influence to stabilize
        dx, dy = ((lx+rx)/2 - nose.x) * 10 + 0.5, ((ly+ry)/2 - nose.y) * 10 + 0.5
        return max(0, min(1, dx)), max(0, min(1, dy))

    def map_to_screen(val, margin=0.35):
        # Increased margin to 0.35. 
        # This SMALLER active area means HIGHER sensitivity (less hand movement needed)
        # and keeps the hand closer to the center of the camera, providing "headroom"
        # to perform clicks even at the very edges of the screen.
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
        
        # Reset current frame key detections to False
        detected_keys_this_frame = {'w': False, 'd': False, 'k': False, 'p': False}
        
        two_hand_zoom_active = False
        
        if hand_results.multi_hand_landmarks:
            right_idx, left_idx = -1, -1
            for i, handedness in enumerate(hand_results.multi_handedness):
                if handedness.classification[0].label == "Right": right_idx = i
                else: left_idx = i
            
            if right_idx != -1 or left_idx != -1:
                hand_detected = True
            
            # Detect two-handed zoom state (both hands pinching thumb and index)
            if right_idx != -1 and left_idx != -1:
                l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                if get_dist(l_lms[4], l_lms[8]) < 0.05 and get_dist(r_lms[4], r_lms[8]) < 0.05:
                    two_hand_zoom_active = True
                    # Use center point of both hands for zoom distance
                    curr_h2h_dist = get_dist(l_lms[9], r_lms[9])
                    if last_two_hand_zoom_dist != 0:
                        dz = curr_h2h_dist - last_two_hand_zoom_dist
                        if abs(dz) > ZOOM_SENSITIVITY:
                            with keyboard.pressed(Key.ctrl):
                                mouse.scroll(0, 1 if dz > 0 else -1)
                            last_two_hand_zoom_dist = curr_h2h_dist
                    else:
                        last_two_hand_zoom_dist = curr_h2h_dist
                else:
                    last_two_hand_zoom_dist = 0
            else:
                last_two_hand_zoom_dist = 0

            # --- Left Hand ---
            if left_idx != -1 and not two_hand_zoom_active:
                l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                
                # Mode Toggle: Must hold pinch between thumb and pinky (4, 20)
                # Increased threshold from 0.04 to 0.06 and reduced time from 1.5s to 1.0s for better response.
                if get_dist(l_lms[4], l_lms[20]) < 0.06:
                    if rhythm_toggle_start_time == 0:
                        rhythm_toggle_start_time = time.time()
                    elif time.time() - rhythm_toggle_start_time > 1.0:
                        if time.time() - last_rhythm_toggle_time > 1.0:
                            rhythm_mode = not rhythm_mode
                            last_rhythm_toggle_time = time.time()
                            rhythm_toggle_start_time = 0
                            print(f"DEBUG: Rhythm Mode Switched to {rhythm_mode}")
                else:
                    rhythm_toggle_start_time = 0
                
                # Rhythm Keys (w, d)
                if rhythm_mode:
                    # W key (Left Middle)
                    ratio_w = get_dist(l_lms[12], l_lms[9]) / (get_dist(l_lms[10], l_lms[9]) + 1e-6)
                    vel_w = last_finger_ratios['w'] - ratio_w
                    w_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['w'] else 1.0
                    # Reduced sensitivity from 0.90 to 0.85 to require more deliberate bend
                    detected_keys_this_frame['w'] = (ratio_w < 0.85 * w_mult) or (vel_w > 0.08)
                    last_finger_ratios['w'] = ratio_w

                    # D key (Left Index)
                    ratio_d = get_dist(l_lms[8], l_lms[5]) / (get_dist(l_lms[6], l_lms[5]) + 1e-6)
                    vel_d = last_finger_ratios['d'] - ratio_d
                    d_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['d'] else 1.0
                    # Reduced sensitivity from 0.90 to 0.85
                    detected_keys_this_frame['d'] = (ratio_d < 0.85 * d_mult) or (vel_d > 0.08)
                    last_finger_ratios['d'] = ratio_d
                else:
                    # Volume Control
                    if get_dist(l_lms[4], l_lms[8]) < 0.05:
                        curr = (l_lms[4].x+l_lms[8].x)/2, (l_lms[4].y+l_lms[8].y)/2
                        if last_left_pinch_pos:
                            dy = curr[1]-last_left_pinch_pos[1]
                            if abs(dy) > left_pinch_threshold:
                                keyboard.tap(Key.media_volume_down if dy > 0 else Key.media_volume_up)
                                last_left_pinch_pos = curr
                        else: last_left_pinch_pos = curr
                    else: last_left_pinch_pos = None

            # --- Right Hand ---
            if right_idx != -1 and not two_hand_zoom_active:
                r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                if rhythm_mode:
                    # K key (Right Index)
                    ratio_k = get_dist(r_lms[8], r_lms[5]) / (get_dist(r_lms[6], r_lms[5]) + 1e-6)
                    vel_k = last_finger_ratios['k'] - ratio_k
                    k_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['k'] else 1.0
                    # Reduced sensitivity from 0.99 to 0.92
                    detected_keys_this_frame['k'] = (ratio_k < 0.92 * k_mult) or (vel_k > 0.05)
                    last_finger_ratios['k'] = ratio_k

                    # P key (Right Middle)
                    ratio_p = get_dist(r_lms[12], r_lms[9]) / (get_dist(r_lms[10], r_lms[9]) + 1e-6)
                    vel_p = last_finger_ratios['p'] - ratio_p
                    p_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['p'] else 1.0
                    # Reduced sensitivity from 0.99 to 0.92
                    detected_keys_this_frame['p'] = (ratio_p < 0.92 * p_mult) or (vel_p > 0.05)
                    last_finger_ratios['p'] = ratio_p
                else:
                    # Normal Actions
                    d_idx, d_mid, d_rng = get_dist(r_lms[4], r_lms[8]), get_dist(r_lms[4], r_lms[12]), get_dist(r_lms[4], r_lms[16])
                    
                    # T (Trigger): 0.04
                    # R (Release): 0.06
                    T, R = 0.04, 0.06
                    
                    # Logic to support re-triggering before full release for double click
                    if active_pinch_type == "L":
                        if d_idx < R: current_pinch = "L"
                    elif active_pinch_type == "S":
                        if d_mid < R: current_pinch = "S"
                    elif active_pinch_type == "R":
                        if d_rng < R: current_pinch = "R"
                    
                    if not current_pinch:
                        # Re-trigger before release threshold if distance drops below 0.02
                        if d_idx < 0.02 or d_idx < T: current_pinch = "L"
                        elif d_mid < 0.02 or d_mid < T: current_pinch = "S"
                        elif d_rng < 0.02 or d_rng < T: current_pinch = "R"
                    
                    # Use index finger MCP (landmark 5) for high stability
                    hand_pos = (r_lms[5].x, r_lms[5].y)

                # Productivity Gestures (Swipes)
                if not rhythm_mode:
                    fingers_ext = sum([
                        1 if is_finger_extended(r_lms, 8, 6) else 0,
                        1 if is_finger_extended(r_lms, 12, 10) else 0,
                        1 if is_finger_extended(r_lms, 16, 14) else 0,
                        1 if is_finger_extended(r_lms, 20, 18) else 0
                    ])
                    
                    wrist_x = r_lms[0].x
                    wrist_x_history.append(wrist_x)
                    if len(wrist_x_history) > 5:
                        wrist_x_history.pop(0)
                        
                    if time.time() - last_swipe_time > SWIPE_COOLDOWN and len(wrist_x_history) == 5:
                        dx = wrist_x_history[-1] - wrist_x_history[0]
                        if abs(dx) > SWIPE_THRESHOLD:
                            if fingers_ext == 4: # Open Palm: Virtual Desktop Switch
                                if dx > 0: # Swipe Right
                                    with keyboard.pressed(Key.ctrl), keyboard.pressed(Key.cmd):
                                        keyboard.tap(Key.right)
                                    print("PRODUCTIVITY: Switched Desktop Right")
                                else: # Swipe Left
                                    with keyboard.pressed(Key.ctrl), keyboard.pressed(Key.cmd):
                                        keyboard.tap(Key.left)
                                    print("PRODUCTIVITY: Switched Desktop Left")
                                last_swipe_time = time.time()
                            elif fingers_ext == 0: # Fist: Window Snap
                                if dx > 0:
                                    with keyboard.pressed(Key.cmd):
                                        keyboard.tap(Key.right)
                                    print("PRODUCTIVITY: Snapped Window Right")
                                else:
                                    with keyboard.pressed(Key.cmd):
                                        keyboard.tap(Key.left)
                                    print("PRODUCTIVITY: Snapped Window Left")
                                last_swipe_time = time.time()
            
            # Final check: If NO right hand was detected, we must NOT use any stale hand_pos.
            if right_idx == -1:
                hand_detected = False
                wrist_x_history = [] # Reset history when hand lost

        # --- KEY STATE SYNC (CRITICAL FOR CHORDS/RAPID TAPS) ---
        if rhythm_mode:
            now = time.time()
            for k in ['w', 'd', 'k', 'p']:
                is_detected = detected_keys_this_frame[k]
                if is_detected:
                    if not key_states[k]:
                        if now - last_key_release_time[k] > MIN_KEY_RELEASE_TIME:
                            keyboard.press(k)
                            key_states[k] = True
                            last_key_press_time[k] = now
                else:
                    if key_states[k]:
                        if now - last_key_press_time[k] > MIN_KEY_HOLD_TIME:
                            keyboard.release(k)
                            key_states[k] = False
                            last_key_release_time[k] = now

        # --- Injection & Drawing ---
        if not rhythm_mode:
            now = time.time()
            if current_pinch == "L" and not two_hand_zoom_active:
                if not is_left_down:
                    # If we released recently, and now re-pressed, this might be a double click
                    if now - last_left_click_release_time < DOUBLE_CLICK_THRESHOLD:
                        pending_double_click = True
                    mouse.press(Button.left)
                    is_left_down = True
                    last_left_click_press_time = now
            else:
                if is_left_down:
                    mouse.release(Button.left)
                    is_left_down = False
                    last_left_click_release_time = now
                    if pending_double_click:
                        # Extra tap to ensure double click registration in some apps
                        mouse.click(Button.left, 1)
                        pending_double_click = False

            if current_pinch == "R" and not two_hand_zoom_active:
                if not is_right_down: mouse.press(Button.right); is_right_down = True
            else:
                if is_right_down: mouse.release(Button.right); is_right_down = False

            if current_pinch == "S" and not two_hand_zoom_active:
                cy = r_lms[12].y
                if last_scroll_y != 0:
                    dy = last_scroll_y - cy
                    if abs(dy) > 0.005:
                        mouse.scroll(0, 1 if dy > 0 else -1)
                        last_scroll_y = cy
                else: last_scroll_y = cy
            else:
                last_scroll_y = 0

            # Freeze movement for Right Click, Scroll, or TWO-HAND ZOOM.
            # Left Click (L) MUST allow movement for DRAGGING, but we freeze for a very short duration 
            # when the click FIRST happens to prevent the "jump" when fingers touch.
            freeze = (current_pinch in ["R", "S"]) or two_hand_zoom_active
            
            # Click stabilization: freeze for 150ms on initial click to lock position
            if is_left_down and (time.time() - last_left_click_press_time < 0.15):
                freeze = True

            tx, ty = map_to_screen(hand_pos[0]*0.7 + gaze_x*0.3, 0.33), map_to_screen(hand_pos[1]*0.7 + gaze_y*0.3, 0.33)
            
            p_mask = 0
            if is_left_down: p_mask |= 1 # Bit 0: Left Down (for smoothing alpha in C side)
            if not hand_detected: p_mask |= 16 # Bit 4: Freeze/No-Track
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
        if two_hand_zoom_active: ui_text += " [ZOOMING]"
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
