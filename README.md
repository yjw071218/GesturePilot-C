# GesturePilot-C

CNN + Local AI 기반의 **오프라인 손 제스처 PC 제어 프로젝트**입니다.  
현재 버전은 C 런타임(제스처 안정화/액션 매핑/입력 주입)과 데이터셋/학습 파이프라인을 함께 제공합니다.

## 현재 포함된 것

- C17 기반 런타임 구조
  - 제스처 타입/액션 타입
  - 설정 파일 파서 (`config\gesturepilot.sample.ini`)
  - 시간축 안정화 필터(연속 프레임 + confidence + cooldown)
  - 액션 매퍼
  - Windows `SendInput` 주입
- 추론 모듈 인터페이스 + mock 추론(개발/디버그용)
- 공개 데이터셋 자동 다운로드 스크립트
- 학습 데이터셋 준비 스크립트(0~5 digit -> 6 gesture 클래스)
- PyTorch baseline CNN 학습/ONNX export 스크립트

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
python .\scripts\train_cnn.py --epochs 12 --export-onnx
```

결과물:

```text
models\gesturepilot.pt
models\gesturepilot.onnx
```

## C 런타임 실행

> 기본은 mock 추론 + dry-run 입력입니다.

```powershell
cmake -S . -B build
cmake --build build --config Release
.\build\Release\gesturepilot.exe --config config\gesturepilot.sample.ini
```

## 실시간 카메라 기반 제어 (Python)

완벽하게 학습된 CNN 모델을 사용하여 웹캠에서 실시간으로 손 제스처를 인식합니다:

### 1. 제스처 인식 데모 (시각화만)
```powershell
pip install -r .\scripts\requirements.txt
python .\scripts\gesturepilot_app.py --model models/gesturepilot.onnx --display
```

### 2. 완전한 PC 제어 (마우스/키보드)
```powershell
python .\scripts\gesturepilot_control.py --model models/gesturepilot.onnx --config config/gesturepilot.sample.ini --display
```

**기능:**
- 실시간 카메라 피드에서 손 제스처 인식
- 신뢰도 기반 필터링 (default: 0.80)
- 시간축 안정화 (4연속 프레임 확인)
- 마우스/키보드 자동 제어
- 각 제스처에 대한 신뢰도 점수 표시

**기본 제스처 매핑:**
| 제스처 | 제어 |
|-------|------|
| 손가락 펼침 | 좌클릭 |
| 한 손가락 | 마우스 우측이동 |
| V자 | 마우스 좌측이동 |
| 세 손가락 | 마우스 상단이동 |
| 네 손가락 | 마우스 하단이동 |
| 주먹 | 우클릭 |

**옵션:**
- `--camera <id>`: 카메라 디바이스 ID (기본값: 0)
- `--display`: 비디오 피드 표시 (기본값: 활성화)
- `--no-display`: 비디오 피드 미표시

## 설정 파일 예시

`config\gesturepilot.sample.ini`

- `confidence_threshold`: 최소 신뢰도
- `stable_frames`: 동일 제스처 확정 최소 프레임
- `cooldown_ms`: 동일 액션 재트리거 최소 간격
- `dry_run`: 1이면 키입력 미주입
- `map.<gesture>=<action>` 으로 제스처-액션 연결

## 다음 구현 포인트

1. 웹캠 캡처(예: Media Foundation/SDL2) 추가
2. ONNX Runtime C API 추론 백엔드 추가
3. 실시간 오버레이(FPS, confidence, current gesture) 추가
4. 사용자 캘리브레이션 모드 추가

