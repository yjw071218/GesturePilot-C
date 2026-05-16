"""
@file        tracker.py
@brief       손동작 추적 및 추론 브리지
@details     카메라 프레임에서 손동작을 해석하고 C 코어로 전달한다.
@author      유정우 (yjw071218@korea.ac.kr)
@version     1.2.0
@date        2026-05-17
@copyright   Copyright (c) 2026 Korea University. All rights reserved.
"""
import cv2
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap
import mediapipe as mp
import math
import numpy as np
import time
import queue
import threading
import screen_brightness_control as sbc
import pygetwindow as gw
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

# 이 스크립트는 카메라 프레임을 읽어 손 모양을 해석하고, 결과를 C 코어로 보낸다.
# 기본 원리: 손가락 비율을 열린 상태 기준과 비교해 굽힘 정도를 구하고, 그 변화로 눌림/해제를 나눈다.
# 두 지점 사이의 유클리드 거리를 계산함
def get_dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

# 손가락이 펴져 있는지 확인함 (끝마디와 손목 거리 vs 중간마디와 손목 거리 비교)
def is_finger_extended(hand_lms, tip_idx, pip_idx):
    return get_dist(hand_lms[tip_idx], hand_lms[0]) > get_dist(hand_lms[pip_idx], hand_lms[0])

# 백그라운드에서 웹캠 프레임을 캡처하는 스레드를 시작함
def start_capture_thread(cap):
    frame_queue = queue.Queue(maxsize=2)
    stop_event = threading.Event()

    # 카메라에서 이미지를 계속 읽어오는 루프 함수
    def capture_loop():
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.003)
                continue
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                # 큐가 꽉 차면 오래된 프레임을 버리고 새 프레임을 넣음
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    frame_queue.put_nowait(frame)
                except queue.Full:
                    pass

    # 스레드를 데몬으로 실행하여 메인 프로그램 종료 시 함께 종료되게 함
    capture_thread = threading.Thread(target=capture_loop, name="capture-thread", daemon=True)
    capture_thread.start()
    return frame_queue, stop_event, capture_thread

# 큐에서 가장 최신 프레임을 가져옴
def get_latest_frame(frame_queue, timeout_sec=0.2):
    try:
        frame = frame_queue.get(timeout=timeout_sec)
    except queue.Empty:
        return None

    # 남아있는 모든 프레임을 빼서 가장 마지막 프레임만 유지함
    while True:
        try:
            frame = frame_queue.get_nowait()
        except queue.Empty:
            break
    return frame

# 캡처 스레드를 안전하게 종료함
def stop_capture_thread(stop_event, capture_thread):
    stop_event.set()
    capture_thread.join(timeout=1.0)

# 메인 실행 클래스 (QThread 상속)
class TrackerThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.key_pressed = None
        self.running = True

    def run(self):
        mouse = MouseController()
        keyboard = KeyboardController()
        
        mp_hands = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles

        # MediaPipe Hands 객체를 생성함 (인식률 및 추적률 설정 가능)
        def create_hands(complexity=1, det_conf=0.65, track_conf=0.65):
            return mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=det_conf,
                min_tracking_confidence=track_conf,
                model_complexity=complexity
            )

        # 기본 설정으로 MediaPipe 초기화함
        hands = create_hands(complexity=1, det_conf=0.65, track_conf=0.65)

        # 기본 카메라(0번) 연결함
        cap = cv2.VideoCapture(0)
        if not cap.isOpened(): return

        # 카메라 해상도를 1280x720으로 높이고, 60fps 설정함
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280) 
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, 60)
        
        # 별도 스레드에서 캡처 시작함
        frame_queue, capture_stop_event, capture_thread = start_capture_thread(cap)

        # 전역 상태 관리용 변수들 초기화함
        rhythm_mode = False
        is_frozen_mode = False
        frozen_toggle_start = 0          # 프리즌 모드 토글 시작 시간
        last_rhythm_toggle_time = 0      # 리듬 모드 마지막 전환 시간
        rhythm_toggle_start_time = 0     # 리듬 모드 전환 홀드 시간
        last_left_pinch_pos = None       # 왼손 핀치 이전 좌표
        left_pinch_threshold = 0.04      # 볼륨 조절 작동 임계값
        
        is_left_down = False             # 마우스 좌클릭 상태
        is_right_down = False            # 마우스 우클릭 상태
        active_pinch_type = None         # 현재 활성화된 마우스 동작 종류
        last_scroll_y = 0                # 스크롤 동작 이전 좌표
        
        # 두 손 줌 기능 지원용 변수
        last_two_hand_zoom_dist = 0
        ZOOM_SENSITIVITY = 0.05 
        
        # 일반 모드 더블 클릭 지원용 변수
        last_left_click_release_time = 0
        pending_double_click = False
        DOUBLE_CLICK_THRESHOLD = 0.45 
        last_left_pinch_detect_time = 0
        PINCH_BASE_PRESS_THRESHOLD = 0.03
        PINCH_BASE_RELEASE_THRESHOLD = 0.06
        PINCH_RELEASE_SPEED_BOOST = 0.06
        PINCH_HOLD_GRACE = 0.100
        right_hand_motion_speed = 0.0
        last_right_hand_pos = None
        last_right_hand_sample_time = time.time()
        
        # 포인터 안정화를 위한 적응형 EMA(지수이동평균) 필터 변수
        smooth_x, smooth_y = 0.5, 0.5
        last_raw_x, last_raw_y = 0.5, 0.5
        MIN_ALPHA = 0.05  # 정지 시 강한 필터링 (떨림 방지용)
        MAX_ALPHA = 0.6   # 이동 시 빠른 반응 (지연 최소화용)
        JITTER_THRESHOLD = 0.005 # 미세 떨림 무시 임계값

        # 생산성 제스처 (스와이프) 관련 상태 변수
        last_swipe_time = 0
        wrist_x_history = []
        SWIPE_THRESHOLD = 0.15 
        SWIPE_COOLDOWN = 0.8   
        was_palm_away_fist = False
        
        # 추가 제스처 상태 변수들
        was_task_view_fist = False
        was_maximize_fist = False
        last_left_horizontal_pinch_pos = None
        last_left_brightness_pinch_pos = None
        was_media_fist = False
        last_gesture_msg = ""
        last_gesture_msg_time = 0
        
        # 탭 닫기(가위질) 제스처 상태 변수
        was_scissors_open = False
        last_scissors_time = 0

        # 스크린샷 제스처 상태 변수
        screenshot_latched = False
        screenshot_candidate_start = 0.0
        screenshot_streak = 0
        last_screenshot_time = 0.0
        SCREENSHOT_CONFIRM_FRAMES = 1
        SCREENSHOT_HOLD_TIME = 1.000
        SCREENSHOT_COOLDOWN = 1.000
        SCREENSHOT_WRIST_MIN = 0.03
        SCREENSHOT_CROSS_MAX = 0.12
        
        # 왼손 V-Sign 상태 변수
        was_v_bent = False
        last_v_action_time = 0.0
        V_BEND_ENTER = 0.985
        V_EXTEND_EXIT = 1.000
        V_MEDIA_BLOCK_WINDOW = 0.350
        V_ACTION_COOLDOWN = 0.120

        # 리듬게임 모드용 키별 상태 및 시간 기록
        key_states = {'w': False, 'd': False, 'k': False, 'p': False}
        last_key_press_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
        last_key_release_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
        last_detected_time = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
        
        # 리듬게임 키 감지를 위한 손가락 상대 기준값과 변화량 기록
        rhythm_open_ratio = {'w': 0.0, 'd': 0.0, 'k': 0.0, 'p': 0.0}  # 손가락이 편 상태의 상대 기준값
        last_finger_bend = {'w': 0.0, 'd': 0.0, 'k': 0.0, 'p': 0.0}    # 이전 프레임의 굽힘 정도
        rhythm_press_peak = {'w': 0.0, 'd': 0.0, 'k': 0.0, 'p': 0.0}    # 현재 누름 사이클에서 기록된 최대 굽힘값
        current_finger_ratio = {'w': 0.0, 'd': 0.0, 'k': 0.0, 'p': 0.0}  # 현재 프레임의 손가락 비율 원본값
        
        # 리듬 모드 초저지연 상세 설정값
        MIN_KEY_HOLD_TIME = 0.003
        MIN_KEY_RELEASE_TIME = 0.001
        RELEASE_DEBOUNCE_TIME = 0.006
        RHYTHM_PRESS_CONFIRM_FRAMES = 1
        RHYTHM_RELEASE_CONFIRM_TAP_FRAMES = 1
        RHYTHM_RELEASE_CONFIRM_HOLD_FRAMES = 3
        RHYTHM_RELEASE_GRACE_TAP = 0.012
        RHYTHM_RELEASE_GRACE_HOLD = 0.060
        RHYTHM_HOLD_MODE_AFTER = 0.140
        # 상대 기준으로 판단하므로 손가락이 자신의 "펴진 기준"에서 얼마나 굽었는지만 본다
        RHYTHM_BEND_PRESS_THRESHOLD = 0.032
        RHYTHM_BEND_HOLD_THRESHOLD = 0.022
        RHYTHM_BEND_STRONG_THRESHOLD = 0.055
        RHYTHM_BEND_PRESS_VELOCITY = 0.010
        RHYTHM_BEND_HOLD_VELOCITY = 0.007
        RHYTHM_BEND_STRONG_VELOCITY = 0.015
        RHYTHM_BEND_OPEN_GATE = 0.015
        RHYTHM_BEND_OPEN_VELOCITY = 0.005
        RHYTHM_FORCE_RELEASE_BEND = 0.012
        RHYTHM_RELEASE_FROM_PEAK_RATIO = 0.18
        RHYTHM_RIGHT_BEND_PRESS_THRESHOLD = 0.022  # 오른손 K/P 눌림 시작 기준
        RHYTHM_RIGHT_BEND_HOLD_THRESHOLD = 0.016   # 오른손 K/P 유지 기준
        RHYTHM_RIGHT_BEND_STRONG_THRESHOLD = 0.040 # 오른손 K/P 확실한 눌림 기준
        RHYTHM_RIGHT_BEND_PRESS_VELOCITY = 0.007   # 오른손 K/P 눌림 변화 속도 기준
        RHYTHM_RIGHT_BEND_HOLD_VELOCITY = 0.005    # 오른손 K/P 유지 변화 속도 기준
        RHYTHM_RIGHT_BEND_STRONG_VELOCITY = 0.010  # 오른손 K/P 강한 변화 속도 기준
        RHYTHM_RIGHT_FORCE_RELEASE_BEND = 0.026     # 오른손 K/P 즉시 해제용 절대 굽힘 기준
        RHYTHM_RIGHT_FORCE_RELEASE_VELOCITY = 0.006 # 오른손 K/P 즉시 해제용 변화 속도 기준
        RHYTHM_HAND_CLASS_SCORE = 0.58
        NORMAL_HAND_CLASS_SCORE = 0.72
        RHYTHM_MISSING_HAND_GRACE = 0.050
        RHYTHM_NO_HAND_RELEASE = 0.085
        rhythm_hit_streak = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
        rhythm_miss_streak = {'w': 0, 'd': 0, 'k': 0, 'p': 0}
        last_key_hand_seen = {'w': 0.0, 'd': 0.0, 'k': 0.0, 'p': 0.0}
        current_rhythm_bend = {'w': 0.0, 'd': 0.0, 'k': 0.0, 'p': 0.0}
        # 순간값과 EMA 값을 같이 보아 짧은 흔들림은 흡수하고 빠른 입력은 놓치지 않게 함
        rhythm_ratio_ema = {'w': 1.0, 'd': 1.0, 'k': 1.0, 'p': 1.0}
        rhythm_velocity_ema = {'w': 0.0, 'd': 0.0, 'k': 0.0, 'p': 0.0}

        # 스무딩 처리 보조 함수 (S-커브)
        def smoothstep01(v):
            v = max(0.0, min(1.0, v))
            return v * v * (3.0 - 2.0 * v)

        # 좌표를 화면 크기에 맞게 매핑함 (가장자리 도달 문제 해결을 위한 S-커브 확장 적용)
        def map_to_screen(val, margin=0.30, edge_precision=0.70):
            normalized = max(0.0, min(1.0, (val - margin) / (1.0 - 2.0 * margin)))
            if edge_precision <= 0.0:
                res = normalized
            else:
                curved = smoothstep01(normalized)
                res = normalized * (1.0 - edge_precision) + curved * edge_precision
            
            # S-커브 특성상 끝부분이 너무 평탄해져서 모서리에 도달하기 힘든 현상 해결
            # 결과값을 중심(0.5) 기준으로 1.10배 확장하여 화면 끝(0.0 및 1.0)에 아주 쉽게 닿도록 함
            res = (res - 0.5) * 1.10 + 0.5
            return max(0.0, min(1.0, res))

        # 손 크기에 맞춰 핀치 임계값을 동적으로 조절함
        def adaptive_pinch_thresholds(hand_lms, press_base=0.035, release_base=0.060):
            palm_span = get_dist(hand_lms[5], hand_lms[17]) + 1e-6
            press_t = max(press_base, min(0.055, palm_span * 0.58))
            release_t = max(release_base, min(0.095, palm_span * 1.00))
            return press_t, release_t

        # 손이 사라졌을 때 리듬 키 상태를 즉시 정리함
        def release_rhythm_keys(key_names):
            for key_name in key_names:
                if key_states[key_name]:
                    keyboard.release(key_name)
                    key_states[key_name] = False
                rhythm_hit_streak[key_name] = 0
                rhythm_miss_streak[key_name] = 0
                last_key_press_time[key_name] = 0.0
                last_key_release_time[key_name] = time.time()
                last_detected_time[key_name] = 0.0
                last_key_hand_seen[key_name] = 0.0
                rhythm_ratio_ema[key_name] = 0.0
                rhythm_velocity_ema[key_name] = 0.0
                last_finger_bend[key_name] = 0.0
                rhythm_press_peak[key_name] = 0.0
                current_finger_ratio[key_name] = 0.0

        # 현재 press의 최대 굽힘값을 이용해 열린 기준값을 새로 계산함
        def recalibrate_rhythm_open_ratio(key_name):
            peak_bend = rhythm_press_peak[key_name]
            sample_ratio = current_finger_ratio[key_name]
            if peak_bend <= 0.0 or sample_ratio <= 0.0:
                return
            estimated_open = sample_ratio / max(0.25, 1.0 - peak_bend)
            rhythm_open_ratio[key_name] = max(0.05, min(2.0, estimated_open))

        prev_loop_time = time.time()
        
        # 메인 처리 루프
        while self.running:
            image = get_latest_frame(frame_queue, timeout_sec=0.25)
            if image is None:
                continue
            loop_now = time.time()
            fps = 1.0 / (loop_now - prev_loop_time + 1e-6)
            prev_loop_time = loop_now

            image = cv2.flip(image, 1) # 좌우 반전하여 거울처럼 보이게 함
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            black_screen = np.zeros(image.shape, dtype=np.uint8)
            
            # 이미지에서 손 랜드마크 추출함
            hand_results = hands.process(image_rgb)

            current_pinch = None
            hand_pos = (0.5, 0.5)
            hand_detected = False
            
            detected_keys_this_frame = {'w': False, 'd': False, 'k': False, 'p': False}
            key_hand_present = {'w': False, 'd': False, 'k': False, 'p': False}
            two_hand_zoom_active = False
            screenshot_rectangle_active = False
            
            is_palm_away_right = False
            is_palm_away_left = False
            
            right_idx, left_idx = -1, -1
            
            if hand_results.multi_hand_landmarks:
                # 왼손, 오른손 인덱스 분리함
                for i, handedness in enumerate(hand_results.multi_handedness):
                    # 인식 신뢰도가 낮으면 무시함 (오인식 방지용)
                    class_score_threshold = RHYTHM_HAND_CLASS_SCORE if rhythm_mode else NORMAL_HAND_CLASS_SCORE
                    if handedness.classification[0].score < class_score_threshold: continue
                    if handedness.classification[0].label == "Right": right_idx = i
                    else: left_idx = i
                
                # 손등이 화면을 향하는지 확인함
                if right_idx != -1:
                    r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                    is_palm_away_right = r_lms[5].x > r_lms[17].x
                if left_idx != -1:
                    l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                    is_palm_away_left = l_lms[17].x > l_lms[5].x

                # 어느 한 손이라도 손바닥이 보이면 인식된 것으로 처리함
                if (right_idx != -1 and not is_palm_away_right) or (left_idx != -1 and not is_palm_away_left):
                    hand_detected = True
                
                # --- 양손 제스처 처리 구역 ---
                if right_idx != -1 and left_idx != -1 and not is_frozen_mode:
                    l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                    r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                    
                    # 1. 양손 줌 제스처 처리함 (리듬 모드에서는 비활성화)
                    if (not rhythm_mode) and get_dist(l_lms[4], l_lms[8]) < 0.05 and get_dist(r_lms[4], r_lms[8]) < 0.05:
                        two_hand_zoom_active = True
                        curr_h2h_dist = get_dist(l_lms[9], r_lms[9])
                        if last_two_hand_zoom_dist != 0:
                            dz = curr_h2h_dist - last_two_hand_zoom_dist
                            if abs(dz) > ZOOM_SENSITIVITY:
                                with keyboard.pressed(Key.ctrl):
                                    mouse.scroll(0, 1 if dz > 0 else -1) # Ctrl + 스크롤로 줌 인/아웃
                                last_two_hand_zoom_dist = curr_h2h_dist
                        else:
                            last_two_hand_zoom_dist = curr_h2h_dist
                    else:
                        last_two_hand_zoom_dist = 0

                    # 2. 스크린샷 (왼엄지-오검지 및 왼검지-오엄지 교차 터치) 처리함
                    if not rhythm_mode:
                        l_thumb, l_index = l_lms[4], l_lms[8]
                        r_thumb, r_index = r_lms[4], r_lms[8]
                        cross_a = get_dist(l_thumb, r_index)
                        cross_b = get_dist(l_index, r_thumb)
                        screenshot_candidate = (
                            get_dist(l_lms[0], r_lms[0]) > SCREENSHOT_WRIST_MIN and
                            cross_a < SCREENSHOT_CROSS_MAX and
                            cross_b < SCREENSHOT_CROSS_MAX
                        )
                        if screenshot_candidate:
                            screenshot_rectangle_active = True
                            screenshot_streak = min(60, screenshot_streak + 1)
                            if screenshot_candidate_start == 0.0:
                                screenshot_candidate_start = loop_now
                            # 일정 시간 유지 시 스크린샷 단축키 전송함
                            if (not screenshot_latched) and \
                               (screenshot_streak >= SCREENSHOT_CONFIRM_FRAMES) and \
                               (loop_now - screenshot_candidate_start >= SCREENSHOT_HOLD_TIME) and \
                               (loop_now - last_screenshot_time >= SCREENSHOT_COOLDOWN):
                                with keyboard.pressed(Key.cmd), keyboard.pressed(Key.shift):
                                    keyboard.tap('s') # Windows 스크린샷 단축키 (Win+Shift+S)
                                screenshot_latched = True
                                last_screenshot_time = loop_now
                                last_gesture_msg, last_gesture_msg_time = "SCREENSHOT", time.time()
                        else:
                            screenshot_rectangle_active = False
                            screenshot_streak = 0
                            screenshot_candidate_start = 0.0
                            screenshot_latched = False

                # --- 왼손 전용 제스처 처리 구역 ---
                if left_idx != -1 and not (two_hand_zoom_active or screenshot_rectangle_active) and not is_frozen_mode:
                    l_lms = hand_results.multi_hand_landmarks[left_idx].landmark
                    
                    # 리듬게임 모드 전환: 왼손 엄지와 새끼손가락을 맞대고 1초 유지함
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
                                    # 리듬 모드 해제 시 모든 키 입력을 강제로 뗌
                                    if not rhythm_mode:
                                        for key_name in ['w', 'd', 'k', 'p']:
                                            if key_states[key_name]:
                                                keyboard.release(key_name)
                                                key_states[key_name] = False
                                                last_key_release_time[key_name] = time.time()
                                            rhythm_hit_streak[key_name] = 0
                                            rhythm_miss_streak[key_name] = 0
                                    hands.close()
                                    # 모드에 따라 MediaPipe 인식률을 조정하여 재초기화함
                                    if rhythm_mode:
                                        hands = create_hands(complexity=1, det_conf=0.60, track_conf=0.60)
                                    else:
                                        hands = create_hands(complexity=1, det_conf=0.65, track_conf=0.65)
                        else:
                            rhythm_toggle_start_time = 0
                    else:
                        rhythm_toggle_start_time = 0
                    
                    # 리듬게임 키 감지 (왼손: W, D 키)
                    if rhythm_mode:
                        def get_finger_state(lms, tip, mcp, pip):
                            base_dist = get_dist(lms[mcp], lms[pip]) + 1e-6
                            tip_dist = get_dist(lms[mcp], lms[tip])
                            return tip_dist / base_dist

                        key_hand_present['w'] = True
                        key_hand_present['d'] = True

                        # W키는 중지, D키는 검지
                        ratio_w = get_finger_state(l_lms, 12, 9, 10)
                        ratio_d = get_finger_state(l_lms, 8, 5, 6)
                        
                        if rhythm_open_ratio['w'] <= 0.0:
                            rhythm_open_ratio['w'] = ratio_w
                        if rhythm_open_ratio['d'] <= 0.0:
                            rhythm_open_ratio['d'] = ratio_d

                        bend_w = max(0.0, (rhythm_open_ratio['w'] - ratio_w) / max(rhythm_open_ratio['w'], 1e-6))
                        bend_d = max(0.0, (rhythm_open_ratio['d'] - ratio_d) / max(rhythm_open_ratio['d'], 1e-6))
                        vel_w = max(0.0, bend_w - last_finger_bend['w'])
                        vel_d = max(0.0, bend_d - last_finger_bend['d'])

                        current_finger_ratio['w'] = ratio_w
                        current_finger_ratio['d'] = ratio_d
                        if key_states['w']:
                            rhythm_press_peak['w'] = max(rhythm_press_peak['w'], bend_w)
                        else:
                            rhythm_press_peak['w'] = 0.0
                        if key_states['d']:
                            rhythm_press_peak['d'] = max(rhythm_press_peak['d'], bend_d)
                        else:
                            rhythm_press_peak['d'] = 0.0
                        current_rhythm_bend['w'] = bend_w
                        current_rhythm_bend['d'] = bend_d

                        rhythm_ratio_ema['w'] = rhythm_ratio_ema['w'] * 0.60 + bend_w * 0.40
                        rhythm_ratio_ema['d'] = rhythm_ratio_ema['d'] * 0.60 + bend_d * 0.40
                        rhythm_velocity_ema['w'] = rhythm_velocity_ema['w'] * 0.60 + vel_w * 0.40
                        rhythm_velocity_ema['d'] = rhythm_velocity_ema['d'] * 0.60 + vel_d * 0.40
                        w_bend_threshold = RHYTHM_BEND_HOLD_THRESHOLD if key_states['w'] else RHYTHM_BEND_PRESS_THRESHOLD
                        d_bend_threshold = RHYTHM_BEND_HOLD_THRESHOLD if key_states['d'] else RHYTHM_BEND_PRESS_THRESHOLD
                        w_velocity_threshold = RHYTHM_BEND_HOLD_VELOCITY if key_states['w'] else RHYTHM_BEND_PRESS_VELOCITY
                        d_velocity_threshold = RHYTHM_BEND_HOLD_VELOCITY if key_states['d'] else RHYTHM_BEND_PRESS_VELOCITY
                        press_detect_w = (bend_w > w_bend_threshold) and ((vel_w > w_velocity_threshold) or (rhythm_ratio_ema['w'] > w_bend_threshold))
                        press_detect_d = (bend_d > d_bend_threshold) and ((vel_d > d_velocity_threshold) or (rhythm_ratio_ema['d'] > d_bend_threshold))
                        hold_detect_w = bend_w > RHYTHM_BEND_HOLD_THRESHOLD
                        hold_detect_d = bend_d > RHYTHM_BEND_HOLD_THRESHOLD
                        detected_keys_this_frame['w'] = press_detect_w if not key_states['w'] else (hold_detect_w or press_detect_w)
                        detected_keys_this_frame['d'] = press_detect_d if not key_states['d'] else (hold_detect_d or press_detect_d)
                        strong_w = (bend_w > RHYTHM_BEND_STRONG_THRESHOLD) or (vel_w > RHYTHM_BEND_STRONG_VELOCITY) or \
                                   (rhythm_ratio_ema['w'] > RHYTHM_BEND_STRONG_THRESHOLD) or (rhythm_velocity_ema['w'] > RHYTHM_BEND_STRONG_VELOCITY)
                        strong_d = (bend_d > RHYTHM_BEND_STRONG_THRESHOLD) or (vel_d > RHYTHM_BEND_STRONG_VELOCITY) or \
                                   (rhythm_ratio_ema['d'] > RHYTHM_BEND_STRONG_THRESHOLD) or (rhythm_velocity_ema['d'] > RHYTHM_BEND_STRONG_VELOCITY)
                        if strong_w:
                            rhythm_hit_streak['w'] = max(rhythm_hit_streak['w'], RHYTHM_PRESS_CONFIRM_FRAMES)
                        if strong_d:
                            rhythm_hit_streak['d'] = max(rhythm_hit_streak['d'], RHYTHM_PRESS_CONFIRM_FRAMES)
                        
                        last_finger_bend['w'], last_finger_bend['d'] = bend_w, bend_d
                    else:
                        # 일반 모드의 왼손 제스처
                        def get_f_ratio(lms, tip, mcp, pip):
                            upper_joint = get_dist(lms[pip], lms[tip])
                            lower_joint = get_dist(lms[mcp], lms[pip]) + 1e-6
                            return upper_joint / lower_joint

                        r_idx_v = get_f_ratio(l_lms, 8, 5, 6)
                        r_mid_v = get_f_ratio(l_lms, 12, 9, 10)
                        is_other_v_closed = not (is_finger_extended(l_lms, 16, 14) or is_finger_extended(l_lms, 20, 18))
                        v_pose_active = is_other_v_closed and r_idx_v < 1.08 and r_mid_v < 1.08
                        media_blocked_by_v = (time.time() - last_v_action_time < V_MEDIA_BLOCK_WINDOW) or v_pose_active or was_v_bent

                        if not is_palm_away_left:
                            left_press_t, left_release_t = adaptive_pinch_thresholds(l_lms, 0.038, 0.068)
                            ring_press_t = min(0.090, left_press_t * 1.08)

                            # 브라우저 앞/뒤 이동: 검지와 엄지를 맞댄 상태로 좌우로 이동함
                            if get_dist(l_lms[4], l_lms[8]) < left_press_t:
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

                            # 볼륨 조절: 검지와 엄지를 맞댄 상태로 상하로 이동함
                            if get_dist(l_lms[4], l_lms[8]) < left_release_t:
                                curr = (l_lms[4].x+l_lms[8].x)/2, (l_lms[4].y+l_lms[8].y)/2
                                if last_left_pinch_pos:
                                    dy = curr[1]-last_left_pinch_pos[1]
                                    if abs(dy) > left_pinch_threshold:
                                        keyboard.tap(Key.media_volume_down if dy > 0 else Key.media_volume_up)
                                        last_left_pinch_pos = curr
                                        last_gesture_msg, last_gesture_msg_time = "VOLUME", time.time()
                                else: last_left_pinch_pos = curr
                            else: last_left_pinch_pos = None

                            # 화면 밝기 조절: 약지와 엄지를 맞댄 상태로 상하로 이동함
                            if get_dist(l_lms[4], l_lms[16]) < ring_press_t:
                                curr_b = (l_lms[4].x+l_lms[16].x)/2, (l_lms[4].y+l_lms[16].y)/2
                                if last_left_brightness_pinch_pos:
                                    dy_b = curr_b[1] - last_left_brightness_pinch_pos[1]
                                    if abs(dy_b) > 0.05:
                                        try:
                                            curr_bright = sbc.get_brightness()[0]
                                            sbc.set_brightness(max(0, min(100, curr_bright + (-10 if dy_b > 0 else 10))))
                                            last_gesture_msg, last_gesture_msg_time = "BRIGHTNESS", time.time()
                                        except: pass # 밝기 조절 실패 시 에러 무시함 (디버깅용 예외처리)
                                        last_left_brightness_pinch_pos = curr_b
                                else: last_left_brightness_pinch_pos = curr_b
                            else: last_left_brightness_pinch_pos = None
                            
                            # 미디어 재생/일시정지: 왼손 주먹을 쥠
                            is_l_fist = sum([1 if is_finger_extended(l_lms, t, p) else 0 for t, p in [(8,6), (12,10), (16,14), (20,18)]]) == 0
                            if not media_blocked_by_v:
                                if is_l_fist and not was_media_fist:
                                    keyboard.tap(Key.media_play_pause)
                                    was_media_fist = True
                                    last_gesture_msg, last_gesture_msg_time = "PLAY/PAUSE", time.time()
                                elif not is_l_fist and was_media_fist:
                                    was_media_fist = False
                            else:
                                was_media_fist = False

                        # 복사/붙여넣기: 검지와 중지로 V자를 만들어 굽혔다 폄
                        if is_other_v_closed:
                            if r_idx_v < V_BEND_ENTER and r_mid_v < V_BEND_ENTER:
                                was_v_bent = True
                            elif r_idx_v > V_EXTEND_EXIT and r_mid_v > V_EXTEND_EXIT and was_v_bent:
                                if time.time() - last_v_action_time > V_ACTION_COOLDOWN:
                                    if not is_palm_away_left: # 정방향일 때는 붙여넣기 (Ctrl+V)
                                        with keyboard.pressed(Key.ctrl): keyboard.tap('v')
                                        last_gesture_msg, last_gesture_msg_time = "PASTE (Ctrl+V)", time.time()
                                    else: # 뒤집힌 상태일 때는 복사 (Ctrl+C)
                                        with keyboard.pressed(Key.ctrl): keyboard.tap('c')
                                        last_gesture_msg, last_gesture_msg_time = "COPY (Ctrl+C)", time.time()
                                    last_v_action_time = time.time()
                                was_v_bent = False
                        else:
                            was_v_bent = False

                if left_idx == -1:
                    if rhythm_mode and not is_frozen_mode:
                        release_rhythm_keys(['w', 'd'])
                    last_left_pinch_pos = None
                    last_left_brightness_pinch_pos = None
                    last_left_horizontal_pinch_pos = None
                    was_media_fist = False
                    was_v_bent = False

                # --- 오른손 전용 제스처 처리 구역 ---
                if right_idx != -1 and not (two_hand_zoom_active or screenshot_rectangle_active):
                    r_lms = hand_results.multi_hand_landmarks[right_idx].landmark
                    
                    # 프리즌 모드 토글: 오른손 엄지와 새끼손가락을 맞대고 1초 유지함
                    if not is_palm_away_right:
                        if get_dist(r_lms[4], r_lms[20]) < 0.08:
                            if frozen_toggle_start == 0:
                                frozen_toggle_start = time.time()
                            elif time.time() - frozen_toggle_start > 1.0:
                                is_frozen_mode = not is_frozen_mode
                                frozen_toggle_start = time.time() + 1.0 # 쿨다운
                                last_gesture_msg = f"FROZEN {'ON' if is_frozen_mode else 'OFF'}"
                                last_gesture_msg_time = time.time()
                        else:
                            if frozen_toggle_start > 0 and time.time() > frozen_toggle_start:
                                frozen_toggle_start = 0
                                
                    # 프리즌 모드일 경우 오른손의 나머지 모든 기능 무시함
                    if not is_frozen_mode:
                        if rhythm_mode:
                            # 오른손 리듬게임 키 감지 (K: 검지, P: 중지)
                            def get_finger_state(lms, tip, mcp, pip):
                                base_dist = get_dist(lms[mcp], lms[pip]) + 1e-6
                                tip_dist = get_dist(lms[mcp], lms[tip])
                                return tip_dist / base_dist

                            key_hand_present['k'] = True
                            key_hand_present['p'] = True

                            ratio_k = get_finger_state(r_lms, 8, 5, 6)
                            ratio_p = get_finger_state(r_lms, 12, 9, 10)

                            if rhythm_open_ratio['k'] <= 0.0:
                                rhythm_open_ratio['k'] = ratio_k
                            if rhythm_open_ratio['p'] <= 0.0:
                                rhythm_open_ratio['p'] = ratio_p

                            bend_k = max(0.0, (rhythm_open_ratio['k'] - ratio_k) / max(rhythm_open_ratio['k'], 1e-6))
                            bend_p = max(0.0, (rhythm_open_ratio['p'] - ratio_p) / max(rhythm_open_ratio['p'], 1e-6))
                            vel_k = max(0.0, bend_k - last_finger_bend['k'])
                            vel_p = max(0.0, bend_p - last_finger_bend['p'])

                            current_finger_ratio['k'] = ratio_k
                            current_finger_ratio['p'] = ratio_p

                            if key_states['k']:
                                rhythm_press_peak['k'] = max(rhythm_press_peak['k'], bend_k)
                            else:
                                rhythm_press_peak['k'] = 0.0
                            if key_states['p']:
                                rhythm_press_peak['p'] = max(rhythm_press_peak['p'], bend_p)
                            else:
                                rhythm_press_peak['p'] = 0.0
                            current_rhythm_bend['k'] = bend_k
                            current_rhythm_bend['p'] = bend_p

                            rhythm_ratio_ema['k'] = rhythm_ratio_ema['k'] * 0.60 + bend_k * 0.40
                            rhythm_ratio_ema['p'] = rhythm_ratio_ema['p'] * 0.60 + bend_p * 0.40
                            rhythm_velocity_ema['k'] = rhythm_velocity_ema['k'] * 0.60 + vel_k * 0.40
                            rhythm_velocity_ema['p'] = rhythm_velocity_ema['p'] * 0.60 + vel_p * 0.40
                            k_bend_threshold = RHYTHM_RIGHT_BEND_HOLD_THRESHOLD if key_states['k'] else RHYTHM_RIGHT_BEND_PRESS_THRESHOLD
                            p_bend_threshold = RHYTHM_RIGHT_BEND_HOLD_THRESHOLD if key_states['p'] else RHYTHM_RIGHT_BEND_PRESS_THRESHOLD
                            k_velocity_threshold = RHYTHM_RIGHT_BEND_HOLD_VELOCITY if key_states['k'] else RHYTHM_RIGHT_BEND_PRESS_VELOCITY
                            p_velocity_threshold = RHYTHM_RIGHT_BEND_HOLD_VELOCITY if key_states['p'] else RHYTHM_RIGHT_BEND_PRESS_VELOCITY
                            press_detect_k = (bend_k > k_bend_threshold) and ((vel_k > k_velocity_threshold) or (rhythm_ratio_ema['k'] > k_bend_threshold))
                            press_detect_p = (bend_p > p_bend_threshold) and ((vel_p > p_velocity_threshold) or (rhythm_ratio_ema['p'] > p_bend_threshold))
                            hold_detect_k = bend_k > RHYTHM_BEND_HOLD_THRESHOLD
                            hold_detect_p = bend_p > RHYTHM_BEND_HOLD_THRESHOLD
                            detected_keys_this_frame['k'] = press_detect_k if not key_states['k'] else (hold_detect_k or press_detect_k)
                            detected_keys_this_frame['p'] = press_detect_p if not key_states['p'] else (hold_detect_p or press_detect_p)
                            strong_k = (bend_k > RHYTHM_RIGHT_BEND_STRONG_THRESHOLD) or (vel_k > RHYTHM_RIGHT_BEND_STRONG_VELOCITY) or \
                                       (rhythm_ratio_ema['k'] > RHYTHM_RIGHT_BEND_STRONG_THRESHOLD) or (rhythm_velocity_ema['k'] > RHYTHM_RIGHT_BEND_STRONG_VELOCITY)
                            strong_p = (bend_p > RHYTHM_RIGHT_BEND_STRONG_THRESHOLD) or (vel_p > RHYTHM_RIGHT_BEND_STRONG_VELOCITY) or \
                                       (rhythm_ratio_ema['p'] > RHYTHM_RIGHT_BEND_STRONG_THRESHOLD) or (rhythm_velocity_ema['p'] > RHYTHM_RIGHT_BEND_STRONG_VELOCITY)
                            if strong_k:
                                rhythm_hit_streak['k'] = max(rhythm_hit_streak['k'], RHYTHM_PRESS_CONFIRM_FRAMES)
                            if strong_p:
                                rhythm_hit_streak['p'] = max(rhythm_hit_streak['p'], RHYTHM_PRESS_CONFIRM_FRAMES)

                            last_finger_bend['k'], last_finger_bend['p'] = bend_k, bend_p
                        else:
                            if not is_palm_away_right:
                                # 일반 마우스 동작: 엄지와 다른 손가락(검지, 중지, 약지)의 거리를 측정하여 클릭 및 스크롤을 구현함
                                d_idx, d_mid, d_rng = get_dist(r_lms[4], r_lms[8]), get_dist(r_lms[4], r_lms[12]), get_dist(r_lms[4], r_lms[16])
                                right_now = (r_lms[5].x, r_lms[5].y)
                                right_press_t, right_release_t = adaptive_pinch_thresholds(r_lms, PINCH_BASE_PRESS_THRESHOLD, PINCH_BASE_RELEASE_THRESHOLD)
                                dt_hand = max(0.001, min(0.050, loop_now - last_right_hand_sample_time))
                                if last_right_hand_pos is not None:
                                    inst_hand_speed = math.sqrt((right_now[0] - last_right_hand_pos[0])**2 + (right_now[1] - last_right_hand_pos[1])**2) / dt_hand
                                    right_hand_motion_speed = right_hand_motion_speed * 0.75 + inst_hand_speed * 0.25
                                last_right_hand_pos = right_now
                                last_right_hand_sample_time = loop_now
                                
                                # 더블 클릭 인식을 돕기 위해, 최근에 클릭을 뗐다면 인식 범위를 일시적으로 넓힘
                                is_near_recent_click = (time.time() - last_left_click_release_time < DOUBLE_CLICK_THRESHOLD)
                                release_boost = min(PINCH_RELEASE_SPEED_BOOST, right_hand_motion_speed * 0.020)
                                T = right_press_t
                                R = right_release_t + release_boost + (0.02 if is_near_recent_click else 0.0)

                                # 어떤 핀치(L: 좌클릭, S: 스크롤, R: 우클릭)가 유지되고 있는지 확인함
                                if active_pinch_type == "L":
                                    if d_idx < R: current_pinch = "L"
                                elif active_pinch_type == "S":
                                    if d_mid < R: current_pinch = "S"
                                elif active_pinch_type == "R":
                                    if d_rng < R: current_pinch = "R"
                                
                                # 유지 중인 핀치가 없으면 새로 시작된 핀치를 찾음
                                if not current_pinch:
                                    if d_idx < T: current_pinch = "L"
                                    elif d_mid < T: current_pinch = "S"
                                    elif d_rng < T: current_pinch = "R"
                                if current_pinch == "L":
                                    last_left_pinch_detect_time = loop_now
                                elif active_pinch_type == "L" and is_left_down and (loop_now - last_left_pinch_detect_time < PINCH_HOLD_GRACE):
                                    current_pinch = "L"
                                
                                # 오른손 좌표를 마우스 좌표로 사용함
                                hand_pos = (r_lms[5].x, r_lms[5].y)

                        if not rhythm_mode:
                            fingers_ext = sum([1 if is_finger_extended(r_lms, tip, pip) else 0 for tip, pip in [(8,6), (12,10), (16,14), (20,18)]])
                            
                            # 1. 바탕화면 보기 (Win+D): 손등을 보이고 주먹 쥠
                            if is_palm_away_right:
                                is_fist = fingers_ext == 0
                                if is_fist and not was_palm_away_fist:
                                    with keyboard.pressed(Key.cmd): keyboard.tap('d')
                                    was_palm_away_fist = True
                                    last_gesture_msg, last_gesture_msg_time = "SHOW DESKTOP", time.time()
                                elif not is_fist:
                                    was_palm_away_fist = False
                            else: was_palm_away_fist = False

                            # 2. 작업 보기 (Win+Tab): 손바닥을 보인 채 주먹 쥐고 위로 올림
                            if not is_palm_away_right:
                                is_fist = fingers_ext == 0
                                wrist_y = r_lms[0].y
                                if is_fist:
                                    if not was_task_view_fist and wrist_y < 0.4:
                                        with keyboard.pressed(Key.cmd): keyboard.tap(Key.tab)
                                        was_task_view_fist = True
                                        last_gesture_msg, last_gesture_msg_time = "TASK VIEW", time.time()
                                else: was_task_view_fist = False

                            # 3. 창 최대화/복구: 손바닥을 보인 채 주먹 쥐고 아래로 내림
                            if not is_palm_away_right:
                                is_fist = fingers_ext == 0
                                wrist_y = r_lms[0].y
                                if is_fist:
                                    if not was_maximize_fist and wrist_y > 0.9:
                                        try:
                                            active_win = gw.getActiveWindow()
                                            if active_win:
                                                if active_win.isMaximized:
                                                    with keyboard.pressed(Key.cmd): keyboard.tap(Key.down)
                                                    last_gesture_msg = "RESTORE"
                                                else:
                                                    with keyboard.pressed(Key.cmd): keyboard.tap(Key.up)
                                                    last_gesture_msg = "MAXIMIZE"
                                                last_gesture_msg_time = time.time()
                                        except: pass # 창 제어 실패 시 에러 무시함
                                        was_maximize_fist = True
                                else: was_maximize_fist = False

                            # 4. 탭 닫기 (Ctrl+W): 가위질 제스처 (검지와 중지 벌렸다가 오므리기)
                            if not is_palm_away_right:
                                is_index_ext = is_finger_extended(r_lms, 8, 6)
                                is_middle_ext = is_finger_extended(r_lms, 12, 10)
                                is_other_closed = not (is_finger_extended(r_lms, 16, 14) or is_finger_extended(r_lms, 20, 18))
                                
                                if is_index_ext and is_middle_ext and is_other_closed:
                                    d_scissors = get_dist(r_lms[8], r_lms[12])
                                    if d_scissors > 0.1: # 가위를 벌림
                                        was_scissors_open = True
                                        last_scissors_time = time.time()
                                    elif d_scissors < 0.04 and was_scissors_open: # 가위를 오므림
                                        if time.time() - last_scissors_time < 0.5: # 빠르게 오므려야 인식함
                                            with keyboard.pressed(Key.ctrl):
                                                keyboard.tap('w')
                                            last_gesture_msg, last_gesture_msg_time = "CLOSE TAB (Ctrl+W)", time.time()
                                        was_scissors_open = False
                                else:
                                    if not (is_index_ext and is_middle_ext):
                                        was_scissors_open = False

                            # 5. 스와이프 제스처: 손목의 X좌표 이동 거리를 통해 인식함
                            if not is_palm_away_right:
                                wrist_x = r_lms[0].x
                                wrist_x_history.append(wrist_x)
                                if len(wrist_x_history) > 5: wrist_x_history.pop(0)
                                if time.time() - last_swipe_time > SWIPE_COOLDOWN and len(wrist_x_history) == 5:
                                    dx = wrist_x_history[-1] - wrist_x_history[0]
                                    if abs(dx) > SWIPE_THRESHOLD:
                                        if fingers_ext == 4: # 손가락 4개가 펴져 있으면 데스크톱 전환 (Ctrl+Win+방향키)
                                            with keyboard.pressed(Key.ctrl), keyboard.pressed(Key.cmd):
                                                keyboard.tap(Key.right if dx > 0 else Key.left)
                                            last_swipe_time = time.time()
                                            last_gesture_msg, last_gesture_msg_time = "DESKTOP SWIPE", time.time()
                                        elif fingers_ext == 0: # 주먹 쥔 상태면 창 스냅 (Win+방향키)
                                            with keyboard.pressed(Key.cmd):
                                                keyboard.tap(Key.right if dx > 0 else Key.left)
                                            last_swipe_time = time.time()
                                            last_gesture_msg, last_gesture_msg_time = "WINDOW SNAP", time.time()
                
                if right_idx == -1:
                    if rhythm_mode and not is_frozen_mode:
                        release_rhythm_keys(['k', 'p'])
                    hand_detected = False
                    wrist_x_history = [] 
                    was_palm_away_fist = False
                    was_task_view_fist = False
                    was_scissors_open = False
                    right_hand_motion_speed = right_hand_motion_speed * 0.80

            # --- 리듬게임 모드에서의 키 상태 동기화 처리 ---
            if rhythm_mode and not is_frozen_mode:
                now = time.time()
                for k in ['w', 'd', 'k', 'p']:
                    if key_hand_present[k]:
                        last_key_hand_seen[k] = now

                    hand_present_recent = (now - last_key_hand_seen[k]) <= RHYTHM_NO_HAND_RELEASE
                    raw_detected = detected_keys_this_frame[k]
                    grace_detected = (not raw_detected) and key_states[k] and hand_present_recent and ((now - last_detected_time[k]) < RHYTHM_MISSING_HAND_GRACE)
                    effective_detected = raw_detected or grace_detected
                    if k in ['k', 'p']:
                        release_bend_limit = RHYTHM_RIGHT_FORCE_RELEASE_BEND
                        release_velocity_limit = RHYTHM_RIGHT_FORCE_RELEASE_VELOCITY
                    else:
                        release_bend_limit = RHYTHM_BEND_HOLD_THRESHOLD * 1.25
                        release_velocity_limit = RHYTHM_BEND_HOLD_VELOCITY * 1.50

                    # 손이 사라진 상태에서 키가 눌려있으면 즉시 강제로 뗌
                    if (not hand_present_recent) and key_states[k]:
                        keyboard.release(k); key_states[k] = False; last_key_release_time[k] = now
                        rhythm_hit_streak[k] = 0
                        rhythm_miss_streak[k] = 0
                        recalibrate_rhythm_open_ratio(k)
                        rhythm_press_peak[k] = 0.0
                        current_rhythm_bend[k] = 0.0
                        last_detected_time[k] = 0.0
                        continue

                    if effective_detected:
                        rhythm_hit_streak[k] = min(rhythm_hit_streak[k] + 1, 8)
                        rhythm_miss_streak[k] = 0
                        if raw_detected:
                            last_detected_time[k] = now
                        # 조건 만족 시 키보드 입력(Press) 수행함
                        if not key_states[k]:
                            if now - last_key_release_time[k] > MIN_KEY_RELEASE_TIME:
                                if rhythm_hit_streak[k] >= RHYTHM_PRESS_CONFIRM_FRAMES:
                                    keyboard.press(k); key_states[k] = True; last_key_press_time[k] = now
                    elif key_states[k]:
                        rhythm_hit_streak[k] = max(0, rhythm_hit_streak[k] - 1)
                        rhythm_miss_streak[k] = min(rhythm_miss_streak[k] + 1, 8)
                        key_hold_duration = now - last_key_press_time[k]
                        current_bend = current_rhythm_bend[k]
                        peak_bend = rhythm_press_peak[k]
                        reopened_ratio = 1.0
                        if peak_bend > 1e-6:
                            reopened_ratio = (peak_bend - current_bend) / peak_bend
                        # 유지 시간에 따라 뗌(Release) 인식을 위한 여유 프레임을 다르게 설정함
                        if key_hold_duration > RHYTHM_HOLD_MODE_AFTER:
                            release_grace = RHYTHM_RELEASE_GRACE_HOLD * 0.45
                            release_confirm_frames = 1
                        else:
                            release_grace = RHYTHM_RELEASE_GRACE_TAP * 0.45
                            release_confirm_frames = 1
                        # 조건 만족 시 키보드 입력 뗌(Release) 수행함
                        if (now - last_key_press_time[k] > MIN_KEY_HOLD_TIME) and \
                           ((current_bend <= RHYTHM_FORCE_RELEASE_BEND) or \
                            (reopened_ratio >= RHYTHM_RELEASE_FROM_PEAK_RATIO) or \
                            (current_bend < release_bend_limit and rhythm_miss_streak[k] >= release_confirm_frames and \
                             (now - last_detected_time[k] > max(RELEASE_DEBOUNCE_TIME, release_grace) or current_rhythm_bend[k] < release_velocity_limit))):
                            recalibrate_rhythm_open_ratio(k)
                            keyboard.release(k); key_states[k] = False; last_key_release_time[k] = now
                            rhythm_press_peak[k] = 0.0
                            current_rhythm_bend[k] = 0.0
                    else:
                        rhythm_hit_streak[k] = max(0, rhythm_hit_streak[k] - 1)
                        rhythm_miss_streak[k] = 0

            # --- 마우스 및 화면 출력 업데이트 처리 ---
            if is_frozen_mode:
                current_pinch = None
                is_left_down = False
                is_right_down = False
                two_hand_zoom_active = False
                screenshot_rectangle_active = False

            if not rhythm_mode:
                now = time.time()
                if is_left_down and active_pinch_type == "L" and current_pinch != "L" and (now - last_left_pinch_detect_time < PINCH_HOLD_GRACE):
                    current_pinch = "L"
                
                # 좌클릭 제어함
                if current_pinch == "L" and not two_hand_zoom_active:
                    if not is_left_down:
                        if now - last_left_click_release_time < DOUBLE_CLICK_THRESHOLD: pending_double_click = True
                        mouse.press(Button.left); is_left_down = True; last_left_click_press_time = now
                else:
                    if is_left_down:
                        mouse.release(Button.left); is_left_down = False; last_left_click_release_time = now
                        if pending_double_click: mouse.click(Button.left, 1); pending_double_click = False

                # 우클릭 제어함
                if current_pinch == "R" and not two_hand_zoom_active:
                    if not is_right_down: mouse.press(Button.right); is_right_down = True
                else:
                    if is_right_down: mouse.release(Button.right); is_right_down = False

                # 마우스 스크롤 처리함
                if current_pinch == "S" and not two_hand_zoom_active:
                    cy = r_lms[12].y
                    if last_scroll_y != 0:
                        dy = last_scroll_y - cy
                        if abs(dy) > 0.005: mouse.scroll(0, 1 if dy > 0 else -1); last_scroll_y = cy
                    else: last_scroll_y = cy
                else: last_scroll_y = 0

                # 특정 액션이 실행 중일 때는 커서 이동을 고정(Freeze)시킴
                freeze = (current_pinch in ["R", "S"]) or two_hand_zoom_active or is_palm_away_right or screenshot_rectangle_active
                if is_left_down and (time.time() - last_left_click_press_time < 0.15): freeze = True

                # 좌표를 화면에 맞게 변환하고 적응형 EMA 필터를 적용함
                raw_tx = map_to_screen(hand_pos[0])
                raw_ty = map_to_screen(hand_pos[1])
                
                dist_moved = math.sqrt((raw_tx - last_raw_x)**2 + (raw_ty - last_raw_y)**2)
                
                if dist_moved < JITTER_THRESHOLD:
                    # 미세 떨림 시: 목표 좌표를 이전 좌표로 고정하되, 필터는 최소 알파를 유지하여 커서가 목표점에 완전히 도달하게 함
                    raw_tx, raw_ty = last_raw_x, last_raw_y
                    adaptive_alpha = MIN_ALPHA 
                else:
                    adaptive_alpha = MIN_ALPHA + (MAX_ALPHA - MIN_ALPHA) * min(1.0, dist_moved / 0.05)
                    last_raw_x, last_raw_y = raw_tx, raw_ty
                    
                # 가장자리 근처에서는 커서가 끝까지 즉시 도달하도록 반응성을 강제로 높임
                if raw_tx <= 0.01 or raw_tx >= 0.99 or raw_ty <= 0.01 or raw_ty >= 0.99:
                    adaptive_alpha = max(adaptive_alpha, 0.4)
                
                smooth_x = adaptive_alpha * raw_tx + (1 - adaptive_alpha) * smooth_x
                smooth_y = adaptive_alpha * raw_ty + (1 - adaptive_alpha) * smooth_y
                
                # 마우스 버튼 상태 마스크를 설정하고 표준 출력으로 전송함 (C++ 프로그램에서 받음)
                p_mask = 1 if is_left_down else 0
                if not hand_detected or freeze: p_mask |= 16
                if is_frozen_mode:
                    print(f"none 1.0 0.5 0.5 16 0 0", flush=True)
                else:
                    print(f"{'point' if hand_detected else 'none'} 1.0 {smooth_x:.4f} {smooth_y:.4f} {p_mask} 0 0", flush=True)
            else:
                # 리듬 모드일 때는 마우스 이동 없음 신호를 전송함
                print(f"none 1.0 0.5 0.5 16 0 0", flush=True)

            # 디버깅을 위해 손의 랜드마크를 검은 화면에 그림 (리듬/일반 모드 모두 적용됨)
            if hand_results.multi_hand_landmarks:
                for hand_idx, hand_lms in enumerate(hand_results.multi_hand_landmarks):
                    mp_drawing.draw_landmarks(black_screen, hand_lms, mp_hands.HAND_CONNECTIONS,
                                            mp_drawing_styles.get_default_hand_landmarks_style(),
                                            mp_drawing_styles.get_default_hand_connections_style())
                    
                    # 랜드마크 마다 번호(ID) 디버깅 정보를 출력함
                    for i, lm in enumerate(hand_lms.landmark):
                        cx, cy = int(lm.x * image.shape[1]), int(lm.y * image.shape[0])
                        cv2.putText(black_screen, str(i), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                    
                    # 왼손/오른손 정보를 텍스트로 랜드마크 근처에 출력함 (Flip된 이미지를 기준으로 함)
                    label = hand_results.multi_handedness[hand_idx].classification[0].label
                    cx, cy = int(hand_lms.landmark[0].x * image.shape[1]), int(hand_lms.landmark[0].y * image.shape[0])
                    cv2.putText(black_screen, f"{label} Hand", (cx - 20, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            active_pinch_type = current_pinch
            
            # GUI PIP 기능 (Picture in Picture): 카메라 원본 화면을 좌측 하단에 조그맣게 표시함 (다시 끝에 붙임)
            pip_h, pip_w = int(image.shape[0] * 0.25), int(image.shape[1] * 0.25)
            pip_img = cv2.resize(image, (pip_w, pip_h))
            black_screen[image.shape[0]-pip_h:image.shape[0], 0:pip_w] = pip_img
            
            # 현재 모드 및 상태를 화면에 텍스트로 출력함 (디버깅/사용자용)
            if is_frozen_mode:
                ui_text = "MODE: FROZEN"
            else:
                ui_text = f"MODE: {'RHYTHM' if rhythm_mode else 'NORMAL'}"
                
            if two_hand_zoom_active: ui_text += " [ZOOMING]"
            if screenshot_rectangle_active: ui_text += " [SCREENSHOT]"
            cv2.putText(black_screen, ui_text, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # 제스처가 실행되었을 때 시각적 피드백 제공함
            if time.time() - last_gesture_msg_time < 1.5:
                cv2.putText(black_screen, f"ACTION: {last_gesture_msg}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 3)

            if rhythm_mode:
                active_keys_str = " ".join([k.upper() for k, v in key_states.items() if v])
                if active_keys_str: cv2.putText(black_screen, f"KEYS: {active_keys_str}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # 우측 상단에 확장된 디버깅 정보들을 출력함
            hands_count_str = '2' if (right_idx != -1 and left_idx != -1) else ('1' if hand_detected else '0')
            debug_texts = [
                f"FPS: {fps:.1f}",
                f"FROZEN: {'ON' if is_frozen_mode else 'OFF'}",
                f"HANDS: {hands_count_str} DETECTED",
                f"L-CLICK: {is_left_down}",
                f"R-CLICK: {is_right_down}",
                f"L-PINCH: {last_left_pinch_pos is not None}",
                f"R-PINCH: {current_pinch}",
                f"SMOOTH: {smooth_x:.2f}, {smooth_y:.2f}"
            ]
            
            if rhythm_mode:
                debug_texts.append(f"W-HIT: {rhythm_hit_streak['w']} D-HIT: {rhythm_hit_streak['d']}")
                debug_texts.append(f"K-HIT: {rhythm_hit_streak['k']} P-HIT: {rhythm_hit_streak['p']}")
                
            for i, txt in enumerate(debug_texts):
                cv2.putText(black_screen, txt, (image.shape[1] - 250, 30 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # PyQt5 시그널 전송
            self.change_pixmap_signal.emit(black_screen)
            
            if self.key_pressed == 'q' or not self.running:
                break
            elif self.key_pressed == 'f':
                is_frozen_mode = not is_frozen_mode
                last_gesture_msg = f"FROZEN {'ON' if is_frozen_mode else 'OFF'}"
                last_gesture_msg_time = time.time()
                self.key_pressed = None
            
            time.sleep(0.001)

        # 프로그램 종료 시 자원 해제함
        stop_capture_thread(capture_stop_event, capture_thread)
        cap.release()

class MainWindow(QMainWindow):
    PREVIEW_MARGIN = 24

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GesturePilot - High Performance Tracker")
        # 고정 해상도가 아닌 리사이즈 가능한 초기 크기 설정
        self.resize(1280, 720)
        self.setStyleSheet("background-color: black;")
        
        # 창 내부에 일정한 여백을 두고 이미지를 표시할 전용 라벨을 만든다
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black;")
        self._update_preview_geometry()
        
        self.thread = TrackerThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.start()

    def _update_preview_geometry(self):
        # 창 크기가 바뀌어도 바깥 여백은 항상 동일하게 유지한다
        margin = self.PREVIEW_MARGIN
        width = max(1, self.width() - (margin * 2))
        height = max(1, self.height() - (margin * 2))
        self.image_label.setGeometry(margin, margin, width, height)

    def update_image(self, cv_img):
        # BGR(OpenCV) -> RGB 변환 (색상 보정 유지)
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # 라벨 내부에만 맞춰서 스케일링하므로 창 비율이 변해도 여백이 일정하다
        preview_size = self.image_label.size()
        p = QPixmap.fromImage(convert_to_Qt_format).scaled(preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(p)

    def resizeEvent(self, event):
        # 리사이즈할 때마다 미리보기 영역을 다시 계산한다
        self._update_preview_geometry()
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            self.thread.key_pressed = 'q'
            self.close()
        elif event.key() == Qt.Key_F:
            self.thread.key_pressed = 'f'
        elif event.key() == Qt.Key_F11:
            # F11 전체화면 토글 기능 유지
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            
    def closeEvent(self, event):
        self.thread.running = False
        self.thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
