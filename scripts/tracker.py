import cv2
import mediapipe as mp
import math
import time
import screen_brightness_control as sbc
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

# 두 지점 사이의 유클리드 거리를 계산하는 함수
def get_dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

# 손가락이 펴져 있는지 확인하는 함수 (끝마디와 손목 거리 vs 중간마디와 손목 거리 비교)
def is_finger_extended(hand_lms, tip_idx, pip_idx):
    return get_dist(hand_lms[tip_idx], hand_lms[0]) > get_dist(hand_lms[pip_idx], hand_lms[0])

def main():
    mouse = MouseController()
    keyboard = KeyboardController()
    
    mp_hands = mp.solutions.hands
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    # MediaPipe Hands 객체를 생성하는 헬퍼 함수 (모드 전환 시 복잡도 조절용)
    def create_hands(complexity, conf=0.8):
        return mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=conf, 
            min_tracking_confidence=conf,
            model_complexity=complexity
        )

    # 기본적으로 일반 모드용 높은 정확도 모델(1)로 시작
    hands = create_hands(1, 0.8) 

    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True, 
        min_detection_confidence=0.8,
        min_tracking_confidence=0.8
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened(): return

    # 카메라 성능 최적화 (640x480, 버퍼 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640) 
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # 상태 관리 변수들
    rhythm_mode = False          # 리듬게임 모드 활성화 여부
    last_rhythm_toggle_time = 0  # 마지막 모드 전환 시간
    rhythm_toggle_start_time = 0 # 모드 전환 홀드 시작 시간
    last_left_pinch_pos = None   # 왼손 핀치 위치 (볼륨 조절용)
    left_pinch_threshold = 0.04  # 볼륨 조절 임계값
    
    is_left_down = False         # 마우스 왼쪽 버튼 상태
    is_right_down = False        # 마우스 오른쪽 버튼 상태
    active_pinch_type = None     # 현재 활성화된 핀치 종류
    last_scroll_y = 0            # 마지막 스크롤 위치
    
    # 줌 기능 지원
    last_two_hand_zoom_dist = 0
    ZOOM_SENSITIVITY = 0.05 
    
    # 일반 모드 더블 클릭 지원
    last_left_click_release_time = 0
    pending_double_click = False
    DOUBLE_CLICK_THRESHOLD = 0.45 # 더 넉넉하게 조정
    
    # 포인터 안정화 (Adaptive EMA 필터)
    smooth_x, smooth_y = 0.5, 0.5
    last_raw_x, last_raw_y = 0.5, 0.5
    MIN_ALPHA = 0.05  # 정지 상태에서 매우 강한 필터링 (떨림 방지)
    MAX_ALPHA = 0.6   # 이동 중에는 반응성 우선
    JITTER_THRESHOLD = 0.002 # 미세 떨림 무시 임계값

    # 생산성 제스처 (스와이프) 상태
    last_swipe_time = 0
    wrist_x_history = []
    SWIPE_THRESHOLD = 0.15 
    SWIPE_COOLDOWN = 0.8   
    was_palm_away_fist = False
    
    # New Gesture States
    was_task_view_fist = False
    last_left_horizontal_pinch_pos = None
    last_left_brightness_pinch_pos = None
    was_media_fist = False
    last_gesture_msg = ""
    last_gesture_msg_time = 0
    
    # Scissors States
    was_scissors_open = False
    last_scissors_time = 0
    
    # Left Hand V-Sign States
    was_v_bent = False

    # 키 관리: 현재 실시간 상태 및 시간 기록
    key_states = {'w': False, 'd': False, 'k': False, 'p': False}
    last_key_press_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
    last_key_release_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
    last_detected_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
    
    # 리듬 키 감지용 핑거 비율 기록
    last_finger_ratios = {'w': 1.0, 'd': 1.0, 'k': 1.0, 'p': 1.0}
    
    # 홀드 내성: 키가 눌린 상태에서는 더 둔감하게 판정하여 끊김 방지
    HOLD_SENSITIVITY_MULTIPLIER = 1.60 # 2.2 -> 1.60 (더 빡빡한 릴리스 판정)
    
    # 리듬 모드 초저지연 최소 시간 설정
    MIN_KEY_HOLD_TIME = 0.015 
    MIN_KEY_RELEASE_TIME = 0.010 
    RELEASE_DEBOUNCE_TIME = 0.050 # 0.180 -> 0.050 (즉각적인 릴리스 반응성 확보)

    # 얼굴 랜드마크를 기반으로 시선 지점을 계산하는 함수
    def get_gaze_point(face_landmarks):
        lx = (face_landmarks[474].x + face_landmarks[476].x) / 2
        ly = (face_landmarks[474].y + face_landmarks[476].y) / 2
        rx = (face_landmarks[469].x + face_landmarks[471].x) / 2
        ry = (face_landmarks[469].y + face_landmarks[471].y) / 2
        nose = face_landmarks[168]
        dx, dy = ((lx+rx)/2 - nose.x) * 10 + 0.5, ((ly+ry)/2 - nose.y) * 10 + 0.5
        return max(0, min(1, dx)), max(0, min(1, dy))

    # 좌표를 화면 크기에 맞게 매핑하는 함수 (가장자리 여백 고려)
    def map_to_screen(val, margin=0.35):
        return max(0, min(1, (val - margin) / (1 - 2 * margin)))

    while True:
        success, image = cap.read()
        if not success: continue

        image = cv2.flip(image, 1) # 좌우 반전
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
        
        detected_keys_this_frame = {'w': False, 'd': False, 'k': False, 'p': False}
        two_hand_zoom_active = False
        screenshot_rectangle_active = False
        
        is_palm_away_right = False
        is_palm_away_left = False
        
        if hand_results.multi_hand_landmarks:
            right_idx, left_idx = -1, -1
            for i, handedness in enumerate(hand_results.multi_handedness):
                # 인식 신뢰도가 낮은 경우 무시 (한 손을 두 손으로 오인하는 경우 방지)
                if handedness.classification[0].score < 0.8: continue
                if handedness.classification[0].label == "Right": right_idx = i
                else: left_idx = i
            
            if right_idx != -1:
                r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                is_palm_away_right = r_lms[5].x > r_lms[17].x
            if left_idx != -1:
                l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                is_palm_away_left = l_lms[17].x > l_lms[5].x

            if (right_idx != -1 and not is_palm_away_right) or (left_idx != -1 and not is_palm_away_left):
                hand_detected = True
            
            # --- 양손 제스처 ---
            if right_idx != -1 and left_idx != -1:
                l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                
                # 1. 양손 줌
                if get_dist(l_lms[4], l_lms[8]) < 0.05 and get_dist(r_lms[4], r_lms[8]) < 0.05:
                    two_hand_zoom_active = True
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

                # 2. 스크린샷 (양손 엄지와 검지로 사각형 만들기)
                if not rhythm_mode:
                    l_thumb, l_index = l_lms[4], l_lms[8]
                    r_thumb, r_index = r_lms[4], r_lms[8]
                    # 사각형 모양 감지 및 오인식 방지
                    # - 두 손목 사이의 거리(get_dist(l_lms[0], r_lms[0]))가 최소 0.05 이상이어야 함 (같은 손 오인식 방지)
                    # - 검지간, 엄지간 거리를 더 좁게(0.1) 제한
                    if get_dist(l_lms[0], r_lms[0]) > 0.05 and \
                       get_dist(l_index, r_index) < 0.1 and get_dist(l_thumb, r_thumb) < 0.1 and \
                       l_index.y < l_thumb.y and r_index.y < r_thumb.y:
                        if not screenshot_rectangle_active:
                            with keyboard.pressed(Key.cmd), keyboard.pressed(Key.shift):
                                keyboard.tap('s')
                            screenshot_rectangle_active = True
                            last_gesture_msg, last_gesture_msg_time = "SCREENSHOT", time.time()
                    else:
                        screenshot_rectangle_active = False

            # --- 왼손 처리 ---
            if left_idx != -1 and not (two_hand_zoom_active or screenshot_rectangle_active):
                l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                
                # 모드 전환: 엄지와 새끼손가락을 1초간 맞댐
                if not is_palm_away_left:
                    if get_dist(l_lms[4], l_lms[20]) < 0.06:
                        if rhythm_toggle_start_time == 0:
                            rhythm_toggle_start_time = time.time()
                        elif time.time() - rhythm_toggle_start_time > 1.0:
                            if time.time() - last_rhythm_toggle_time > 1.0:
                                rhythm_mode = not rhythm_mode
                                last_rhythm_toggle_time = time.time()
                                rhythm_toggle_start_time = 0
                                last_gesture_msg, last_gesture_msg_time = "RHYTHM MODE TOGGLED", time.time()
                                hands.close()
                                hands = create_hands(0 if rhythm_mode else 1)
                    else:
                        rhythm_toggle_start_time = 0
                else:
                    rhythm_toggle_start_time = 0
                
                # 리듬 키 감지
                if rhythm_mode:
                    def get_finger_state(lms, tip, mcp, pip):
                        base_dist = get_dist(lms[mcp], lms[pip]) + 1e-6
                        tip_dist = get_dist(lms[mcp], lms[tip])
                        return tip_dist / base_dist

                    # 왼손 (W: 중지, D: 검지)
                    ratio_w = get_finger_state(l_lms, 12, 9, 10)
                    ratio_d = get_finger_state(l_lms, 8, 5, 6)
                    
                    vel_w = last_finger_ratios['w'] - ratio_w
                    vel_d = last_finger_ratios['d'] - ratio_d
                    
                    w_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['w'] else 1.0
                    d_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['d'] else 1.0
                    
                    # 눌리는 판정 완화: 임계값 0.95 -> 0.97, 속도 0.08 -> 0.06
                    detected_keys_this_frame['w'] = (ratio_w < 0.97 * w_mult) or (vel_w > 0.06)
                    detected_keys_this_frame['d'] = (ratio_d < 0.97 * d_mult) or (vel_d > 0.06)
                    
                    last_finger_ratios['w'], last_finger_ratios['d'] = ratio_w, ratio_d
                else:
                    if not is_palm_away_left:
                        # 브라우저 앞/뒤 (검지 핀치 좌우)
                        if get_dist(l_lms[4], l_lms[8]) < 0.06:
                            curr_h = (l_lms[4].x+l_lms[8].x)/2, (l_lms[4].y+l_lms[8].y)/2
                            if last_left_horizontal_pinch_pos:
                                dx_h = curr_h[0] - last_left_horizontal_pinch_pos[0]
                                if abs(dx_h) > 0.1:
                                    with keyboard.pressed(Key.alt):
                                        keyboard.tap(Key.right if dx_h > 0 else Key.left)
                                    last_left_horizontal_pinch_pos = curr_h
                                    last_gesture_msg, last_gesture_msg_time = "BROWSER NAV", time.time()
                            else: last_left_horizontal_pinch_pos = curr_h
                        else: last_left_horizontal_pinch_pos = None

                        # 볼륨 조절 (검지 핀치 상하)
                        if get_dist(l_lms[4], l_lms[8]) < 0.06:
                            curr = (l_lms[4].x+l_lms[8].x)/2, (l_lms[4].y+l_lms[8].y)/2
                            if last_left_pinch_pos:
                                dy = curr[1]-last_left_pinch_pos[1]
                                if abs(dy) > left_pinch_threshold:
                                    keyboard.tap(Key.media_volume_down if dy > 0 else Key.media_volume_up)
                                    last_left_pinch_pos = curr
                                    last_gesture_msg, last_gesture_msg_time = "VOLUME", time.time()
                            else: last_left_pinch_pos = curr
                        else: last_left_pinch_pos = None

                        # 화면 밝기 조절 (약지 핀치 상하)
                        if get_dist(l_lms[4], l_lms[16]) < 0.06:
                            curr_b = (l_lms[4].x+l_lms[16].x)/2, (l_lms[4].y+l_lms[16].y)/2
                            if last_left_brightness_pinch_pos:
                                dy_b = curr_b[1] - last_left_brightness_pinch_pos[1]
                                if abs(dy_b) > 0.05:
                                    try:
                                        curr_bright = sbc.get_brightness()[0]
                                        sbc.set_brightness(max(0, min(100, curr_bright + (-10 if dy_b > 0 else 10))))
                                        last_gesture_msg, last_gesture_msg_time = "BRIGHTNESS", time.time()
                                    except: pass
                                    last_left_brightness_pinch_pos = curr_b
                            else: last_left_brightness_pinch_pos = curr_b
                        else: last_left_brightness_pinch_pos = None
                        
                        # 재생/일시정지 (왼손 주먹)
                        is_l_fist = sum([1 if is_finger_extended(l_lms, t, p) else 0 for t, p in [(8,6), (12,10), (16,14), (20,18)]]) == 0
                        if is_l_fist and not was_media_fist:
                            keyboard.tap(Key.media_play_pause)
                            was_media_fist = True
                            last_gesture_msg, last_gesture_msg_time = "PLAY/PAUSE", time.time()
                        elif not is_l_fist and was_media_fist:
                            was_media_fist = False

                    # V-Sign (검지와 중지만 활성화) - 손가락을 굽혔다 펴면 동작
                    # 딱 위의 한마디(끝마디)만 굽혀도 되도록 비율 계산 방식 변경
                    def get_f_ratio(lms, tip, mcp, pip):
                        # PIP-TIP 거리 대비 MCP-PIP 거리 비율 (끝마디 굽힘 강조)
                        upper_joint = get_dist(lms[pip], lms[tip])
                        lower_joint = get_dist(lms[mcp], lms[pip]) + 1e-6
                        return upper_joint / lower_joint
                    
                    r_idx_v = get_f_ratio(l_lms, 8, 5, 6)
                    r_mid_v = get_f_ratio(l_lms, 12, 9, 10)
                    is_other_v_closed = not (is_finger_extended(l_lms, 16, 14) or is_finger_extended(l_lms, 20, 18))
                    
                    if is_other_v_closed:
                        # 굽힘 판정 (임계값 0.93으로 대폭 완화 - 끝마디만 아주 살짝 굽혀도 됨)
                        if r_idx_v < 0.93 and r_mid_v < 0.93:
                            was_v_bent = True
                        # 펴짐 판정 (임계값 0.96)
                        elif r_idx_v > 0.96 and r_mid_v > 0.96 and was_v_bent:
                            if not is_palm_away_left: # 정방향: 붙여넣기
                                with keyboard.pressed(Key.ctrl): keyboard.tap('v')
                                last_gesture_msg, last_gesture_msg_time = "PASTE (Ctrl+V)", time.time()
                            else: # 뒤집힌 상태: 복사
                                with keyboard.pressed(Key.ctrl): keyboard.tap('c')
                                last_gesture_msg, last_gesture_msg_time = "COPY (Ctrl+C)", time.time()
                            was_v_bent = False
                    else:
                        was_v_bent = False

            if left_idx == -1:
                last_left_pinch_pos = None
                last_left_brightness_pinch_pos = None
                last_left_horizontal_pinch_pos = None
                was_media_fist = False
                was_v_bent = False

            # --- 오른손 처리 ---
            if right_idx != -1 and not (two_hand_zoom_active or screenshot_rectangle_active):
                r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                if rhythm_mode:
                    # 오른손 (K: 검지, P: 중지)
                    def get_finger_state(lms, tip, mcp, pip):
                        base_dist = get_dist(lms[mcp], lms[pip]) + 1e-6
                        tip_dist = get_dist(lms[mcp], lms[tip])
                        return tip_dist / base_dist

                    ratio_k = get_finger_state(r_lms, 8, 5, 6)
                    ratio_p = get_finger_state(r_lms, 12, 9, 10)
                    
                    vel_k = last_finger_ratios['k'] - ratio_k
                    vel_p = last_finger_ratios['p'] - ratio_p
                    
                    k_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['k'] else 1.0
                    p_mult = HOLD_SENSITIVITY_MULTIPLIER if key_states['p'] else 1.0
                    
                    # 눌리는 판정 완화: 임계값 0.95 -> 0.97, 속도 0.08 -> 0.06
                    detected_keys_this_frame['k'] = (ratio_k < 0.97 * k_mult) or (vel_k > 0.06)
                    detected_keys_this_frame['p'] = (ratio_p < 0.97 * p_mult) or (vel_p > 0.08)
                    
                    last_finger_ratios['k'], last_finger_ratios['p'] = ratio_k, ratio_p
                else:
                    if not is_palm_away_right:
                        # 일반 마우스 동작 (엄지와 검지/중지/약지 핀치)
                        d_idx, d_mid, d_rng = get_dist(r_lms[4], r_lms[8]), get_dist(r_lms[4], r_lms[12]), get_dist(r_lms[4], r_lms[16])
                        
                        # 더블 클릭을 돕기 위해, 최근에 클릭을 뗐다면 인식 범위를 일시적으로 확장
                        is_near_recent_click = (time.time() - last_left_click_release_time < DOUBLE_CLICK_THRESHOLD)
                        T, R = (0.06, 0.08) if is_near_recent_click else (0.06, 0.12)

                        if active_pinch_type == "L":
                            if d_idx < R: current_pinch = "L"
                        elif active_pinch_type == "S":
                            if d_mid < R: current_pinch = "S"
                        elif active_pinch_type == "R":
                            if d_rng < R: current_pinch = "R"
                        
                        if not current_pinch:
                            if d_idx < T: current_pinch = "L"
                            elif d_mid < T: current_pinch = "S"
                            elif d_rng < T: current_pinch = "R"
                        
                        hand_pos = (r_lms[5].x, r_lms[5].y)

                if not rhythm_mode:
                    fingers_ext = sum([1 if is_finger_extended(r_lms, tip, pip) else 0 for tip, pip in [(8,6), (12,10), (16,14), (20,18)]])
                    
                    # 1. Win+D (뒤집은 주먹)
                    if is_palm_away_right:
                        is_fist = fingers_ext == 0
                        if is_fist and not was_palm_away_fist:
                            with keyboard.pressed(Key.cmd): keyboard.tap('d')
                            was_palm_away_fist = True
                            last_gesture_msg, last_gesture_msg_time = "SHOW DESKTOP", time.time()
                        elif not is_fist:
                            was_palm_away_fist = False
                    else: was_palm_away_fist = False

                    # 2. Win+Tab (주먹 쥐고 위로)
                    if not is_palm_away_right:
                        is_fist = fingers_ext == 0
                        wrist_y = r_lms[0].y
                        if is_fist:
                            if not was_task_view_fist and wrist_y < 0.4:
                                with keyboard.pressed(Key.cmd): keyboard.tap(Key.tab)
                                was_task_view_fist = True
                                last_gesture_msg, last_gesture_msg_time = "TASK VIEW", time.time()
                        else: was_task_view_fist = False

                    # 3. Ctrl+W (가위질: 검지와 중지 벌렸다가 오므리기)
                    if not is_palm_away_right:
                        # 검지와 중지만 펴져 있는 상태 확인
                        is_index_ext = is_finger_extended(r_lms, 8, 6)
                        is_middle_ext = is_finger_extended(r_lms, 12, 10)
                        is_other_closed = not (is_finger_extended(r_lms, 16, 14) or is_finger_extended(r_lms, 20, 18))
                        
                        if is_index_ext and is_middle_ext and is_other_closed:
                            d_scissors = get_dist(r_lms[8], r_lms[12])
                            if d_scissors > 0.1: # 가위 벌림
                                was_scissors_open = True
                                last_scissors_time = time.time()
                            elif d_scissors < 0.04 and was_scissors_open: # 가위 오므림
                                if time.time() - last_scissors_time < 0.5: # 0.5초 이내의 빠른 동작
                                    with keyboard.pressed(Key.ctrl):
                                        keyboard.tap('w')
                                    last_gesture_msg, last_gesture_msg_time = "CLOSE TAB (Ctrl+W)", time.time()
                                was_scissors_open = False
                        else:
                            if not (is_index_ext and is_middle_ext):
                                was_scissors_open = False

                    # 4. 스와이프 (기존)
                    if not is_palm_away_right:
                        wrist_x = r_lms[0].x
                        wrist_x_history.append(wrist_x)
                        if len(wrist_x_history) > 5: wrist_x_history.pop(0)
                        if time.time() - last_swipe_time > SWIPE_COOLDOWN and len(wrist_x_history) == 5:
                            dx = wrist_x_history[-1] - wrist_x_history[0]
                            if abs(dx) > SWIPE_THRESHOLD:
                                if fingers_ext == 4:
                                    with keyboard.pressed(Key.ctrl), keyboard.pressed(Key.cmd):
                                        keyboard.tap(Key.right if dx > 0 else Key.left)
                                    last_swipe_time = time.time()
                                    last_gesture_msg, last_gesture_msg_time = "DESKTOP SWIPE", time.time()
                                elif fingers_ext == 0:
                                    with keyboard.pressed(Key.cmd):
                                        keyboard.tap(Key.right if dx > 0 else Key.left)
                                    last_swipe_time = time.time()
                                    last_gesture_msg, last_gesture_msg_time = "WINDOW SNAP", time.time()
            
            if right_idx == -1:
                hand_detected = False
                wrist_x_history = [] 
                was_palm_away_fist = False
                was_task_view_fist = False
                was_scissors_open = False

        # --- 키 상태 동기화 (리듬 모드) ---
        if rhythm_mode:
            now = time.time()
            for k in ['w', 'd', 'k', 'p']:
                if detected_keys_this_frame[k]:
                    last_detected_time[k] = now
                    if not key_states[k]:
                        if now - last_key_release_time[k] > MIN_KEY_RELEASE_TIME:
                            keyboard.press(k); key_states[k] = True; last_key_press_time[k] = now
                elif key_states[k]:
                    if (now - last_key_press_time[k] > MIN_KEY_HOLD_TIME) and (now - last_detected_time[k] > RELEASE_DEBOUNCE_TIME):
                        keyboard.release(k); key_states[k] = False; last_key_release_time[k] = now

        # --- 입력 주입 및 화면 출력 ---
        if not rhythm_mode:
            now = time.time()
            if current_pinch == "L" and not two_hand_zoom_active:
                if not is_left_down:
                    if now - last_left_click_release_time < DOUBLE_CLICK_THRESHOLD: pending_double_click = True
                    mouse.press(Button.left); is_left_down = True; last_left_click_press_time = now
            else:
                if is_left_down:
                    mouse.release(Button.left); is_left_down = False; last_left_click_release_time = now
                    if pending_double_click: mouse.click(Button.left, 1); pending_double_click = False

            if current_pinch == "R" and not two_hand_zoom_active:
                if not is_right_down: mouse.press(Button.right); is_right_down = True
            else:
                if is_right_down: mouse.release(Button.right); is_right_down = False

            # 마우스 스크롤 처리
            if current_pinch == "S" and not two_hand_zoom_active:
                cy = r_lms[12].y
                if last_scroll_y != 0:
                    dy = last_scroll_y - cy
                    if abs(dy) > 0.005: mouse.scroll(0, 1 if dy > 0 else -1); last_scroll_y = cy
                else: last_scroll_y = cy
            else: last_scroll_y = 0

            freeze = (current_pinch in ["R", "S"]) or two_hand_zoom_active or is_palm_away_right or screenshot_rectangle_active
            if is_left_down and (time.time() - last_left_click_press_time < 0.15): freeze = True

            # 좌표 변환 및 적응형 EMA 필터링 적용
            raw_tx, raw_ty = map_to_screen(hand_pos[0]*0.7 + gaze_x*0.3, 0.33), map_to_screen(hand_pos[1]*0.7 + gaze_y*0.3, 0.33)
            
            # 이동 속도(변위) 계산
            dist_moved = math.sqrt((raw_tx - last_raw_x)**2 + (raw_ty - last_raw_y)**2)
            
            # 적응형 ALPHA 결정: 많이 움직이면 반응성(높은 ALPHA), 적게 움직이면 안정성(낮은 ALPHA)
            # 0.0 ~ 0.05 범위의 움직임을 0.05 ~ 0.6 ALPHA로 매핑
            adaptive_alpha = MIN_ALPHA + (MAX_ALPHA - MIN_ALPHA) * min(1.0, dist_moved / 0.05)
            
            # 미세 떨림 영역(Dead-zone) 처리: 움직임이 매우 작으면 이전 좌표 유지
            if dist_moved < JITTER_THRESHOLD:
                adaptive_alpha = 0.0 
            
            smooth_x = adaptive_alpha * raw_tx + (1 - adaptive_alpha) * smooth_x
            smooth_y = adaptive_alpha * raw_ty + (1 - adaptive_alpha) * smooth_y
            
            last_raw_x, last_raw_y = raw_tx, raw_ty
            
            p_mask = 1 if is_left_down else 0
            if not hand_detected or freeze: p_mask |= 16
            print(f"{'point' if hand_detected else 'none'} 1.0 {smooth_x:.4f} {smooth_y:.4f} {p_mask} 0 0", flush=True)

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
        if screenshot_rectangle_active: ui_text += " [SCREENSHOT]"
        cv2.putText(image, ui_text, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # 제스처 시각화 피드백
        if time.time() - last_gesture_msg_time < 1.5:
            cv2.putText(image, f"ACTION: {last_gesture_msg}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 3)

        if rhythm_mode:
            active_keys_str = " ".join([k.upper() for k, v in key_states.items() if v])
            if active_keys_str: cv2.putText(image, f"KEYS: {active_keys_str}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow('GesturePilot', image)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
