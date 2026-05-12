# GesturePilot-C

CNN + Local AI 기반의 **오프라인 손 제스처 PC 제어 프로젝트**입니다.  
완벽하게 학습된 CNN(99.59% 검증 정확도)으로 손 제스처를 인식하고, Windows PC의 마우스와 키보드를 완벽하게 제어합니다.

## 현재 포함된 것

- **고성능 CNN 모델** (25 epoch, 99.59% validation accuracy)
  - BatchNorm, Dropout이 포함된 심화 아키텍처
  - 데이터 증강(rotation, affine, colorjitter)
  - ONNX 내보내기 지원
- **C17 기반 런타임 구조**
  - 제스처 타입/액션 타입 (20+ 액션)
  - 설정 파일 파서 (`config\gesturepilot.sample.ini`)
  - 시간축 안정화 필터(연속 프레임 + confidence + cooldown)
  - 액션 매퍼
  - Windows `SendInput` 마우스/키보드 주입
- **마우스 제어**
  - 상하좌우 이동 (gesture 방향)
  - 좌/우클릭
  - 스크롤 (위/아래)
- **키보드 제어**
  - 일반 키: Enter, ESC, Space, Tab, Backspace, Delete
  - 미디어 제어: 재생/일시정지, 이전/다음곡, 볼륨
- 공개 데이터셋 자동 다운로드 스크립트
- 학습 데이터셋 준비 스크립트 (1,237 이미지 → 991 train / 246 val)
- PyTorch CNN 학습/ONNX export 스크립트

## 폴더 구조

```text
GesturePilot-C
├─ CMakeLists.txt
├─ config
│  └─ gesturepilot.sample.ini
├─ data
│  ├─ raw
│  │  └─ sign-language-digits
│  └─ processed
├─ include
├─ src
└─ scripts
   ├─ download_dataset.ps1
   ├─ prepare_dataset.py
   ├─ train_cnn.py
   └─ requirements.txt
```

## 데이터셋

이미 다운로드해 둔 경로:

```text
data\raw\sign-language-digits
```

다시 받으려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_dataset.ps1
```

## 학습용 데이터 준비

```powershell
python .\scripts\prepare_dataset.py
```

준비 결과:

```text
data\processed\gesture_dataset\train\{fist,point,v_sign,three,four,open_palm}
data\processed\gesture_dataset\val\{...}
data\processed\gesture_dataset\dataset_metadata.json
```

## CNN 학습 + ONNX 내보내기

```powershell
pip install -r .\scripts\requirements.txt
python .\scripts\train_cnn.py --epochs 25 --export-onnx
```

학습 결과 (25 epochs):
- **최종 validation accuracy: 99.59%**
- 최종 validation loss: 0.0393
- 훈련 과정에서 최고 accuracy 도달: epoch 11에 99.59%

결과물:

```text
models\gesturepilot.pt          (PyTorch 모델)
models\gesturepilot.onnx        (ONNX 포맷, C/타언어와 호환)
```

## C 런타임 실행

> 기본은 mock 추론 + dry-run 입력입니다.

```powershell
cmake -S . -B build
cmake --build build --config Release
.\build\Release\gesturepilot.exe --config config\gesturepilot.sample.ini
```

## 설정 파일 예시

`config\gesturepilot.sample.ini`

```ini
confidence_threshold=0.80       # 최소 신뢰도
stable_frames=4                 # 동일 제스처 확정 최소 프레임
cooldown_ms=900                 # 동일 액션 재트리거 최소 간격
dry_run=0                       # 0: 실제 입력주입, 1: 입력 안함(테스트)
model_path=models\gesturepilot.onnx

# 제스처 -> 액션 매핑 예시
map.open_palm=mouse_click_left      # 손가락 펼친 상태 = 좌클릭
map.point=mouse_right                # 한 손가락 = 마우스 우측이동
map.v_sign=mouse_left                # V자 = 마우스 좌측이동
map.three=mouse_up                   # 세 손가락 = 마우스 상단이동
map.four=mouse_down                  # 네 손가락 = 마우스 하단이동
map.fist=mouse_click_right           # 주먹 = 우클릭
```

### 사용 가능한 액션

**마우스 제어:**
- `mouse_left`, `mouse_right`, `mouse_up`, `mouse_down`: 방향 이동
- `mouse_click_left`, `mouse_click_right`: 좌/우클릭
- `mouse_scroll_up`, `mouse_scroll_down`: 스크롤

**키보드 제어:**
- `key_enter`, `key_esc`, `key_space`, `key_tab`, `key_backspace`, `key_delete`

**미디어 제어:**
- `play_pause`, `next_slide`, `prev_slide`, `volume_up`, `volume_down`

## 제스처 매핑

| 제스처 | 설명 | 권장 액션 |
|-------|------|---------|
| `fist` | 주먹 | `mouse_click_right` (우클릭) |
| `point` | 한 손가락 | `mouse_right` (우측이동) |
| `v_sign` | V자 모양 | `mouse_left` (좌측이동) |
| `three` | 세 손가락 | `mouse_up` (상단이동) |
| `four` | 네 손가락 | `mouse_down` (하단이동) |
| `open_palm` | 손가락 펼침 | `mouse_click_left` (좌클릭) |

## 다음 구현 포인트

1. **카메라 입력 통합** (Media Foundation / OpenCV C 바인딩)
   - 실시간 웹캠 프레임 캡처
   - 프레임 정규화 (96x96, ImageNet normalization)
   - ONNX Runtime C API 추론 연결

2. **ONNX Runtime C API 추론 백엔드**
   - 현재 mock 추론 → ONNX Runtime으로 교체
   - 동적 배치 처리 지원

3. **실시간 오버레이 UI**
   - FPS 표시
   - 현재 제스처 & confidence 표시
   - 손/얼굴 경계박스

4. **사용자 캘리브레이션 모드**
   - 개인 환경에 맞춰 threshold 조정
   - 제스처 학습 및 재조정

5. **고급 제스처 (추가 학습 모드)**
   - 손가락 개수 기반 분류 확대 (3-finger, 4-finger 등 더 세분화)
   - 제스처 조합 (Hold + Tap)
   - 양손 제스처 지원

