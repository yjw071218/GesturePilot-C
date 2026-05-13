# GesturePilot-C

MediaPipe 기반의 **실시간 손 제스처 PC 제어 프로젝트**입니다.  
카메라를 통해 손의 움직임을 추적하여 마우스를 제어하고, 특정 제스처로 클릭 및 단축키 기능을 수행합니다.

## 주요 기능

- **실시간 마우스 제어**: 검지 손가락 끝을 추적하여 마우스 커서 이동 (절대 좌표)
- **클릭 및 드래그**: 엄지와 검지를 맞대면(Pinch) 좌클릭 및 드래그 실행
- **우클릭**: 주먹을 쥐면(Fist) 마우스 우클릭 실행
- **다양한 액션 매핑**: 손가락 개수에 따른 미디어 제어 및 볼륨 조절
- **지연 시간 최적화**: 저해상도 처리 및 경량 모델 사용으로 반응성 극대화

## 폴더 구조

```text
GesturePilot-C
├─ CMakeLists.txt
├─ config
│  └─ gesturepilot.sample.ini
├─ include
├─ src
└─ scripts
   ├─ tracker.py
   └─ requirements.txt
```

## 실행 방법

### 1. 의존성 설치

```powershell
pip install -r .\scripts\requirements.txt
```

### 2. C 런타임 빌드 및 실행

```powershell
cmake -S . -B build
cmake --build build --config Release
.\build\Release\gesturepilot.exe --config config\gesturepilot.sample.ini
```

또는 제공되는 `run_gesture_pilot.bat` 파일을 실행하십시오.

## 기본 제스처 매핑

| 제스처 | 제어 |
|-------|------|
| 검지 끝 이동 | 마우스 이동 (절대 좌표) |
| 검지+엄지 꼬집기 | 마우스 좌클릭 및 드래그 |
| 주먹 (Fist) | 마우스 우클릭 |
| 손가락 펼침 | 미디어 재생/일시정지 |
| V자 | 이전 슬라이드 |
| 세 손가락 | 볼륨 증가 |
| 네 손가락 | 볼륨 감소 |

## 설정 파일 (`config\gesturepilot.sample.ini`)

- `confidence_threshold`: 제스처 인식 최소 신뢰도
- `stable_frames`: 상태 확정을 위한 프레임 수
- `loop_interval_ms`: 처리 주기 (지연 방지를 위해 1ms 권장)
- `dry_run`: 1이면 실제 입력을 주입하지 않음
- `map.<gesture>=<action>`: 제스처별 액션 커스텀 매핑

