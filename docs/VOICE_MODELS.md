# 목소리·모델 교체

설치가 끝난 Dots Voice의 **설치 폴더**에서 진행한다. 확장에 모델 선택 메뉴는 없으며 JSON 설정을 바꾸고 로컬 서버를 다시 시작하는 방식이다. 현재 설치된 모델이나 목소리는 이 문서를 읽는 것만으로 바뀌지 않는다.

| 바꾸려는 것 | 수정할 값 | 의미 |
| --- | --- | --- |
| 참조 목소리 | `referenceAudio`, `referenceSha256` | 같은 Base 모델에서 새 WAV의 화자 특성을 사용 |
| 합성 모델 | `model`, `revision`, `modelDirectory` | 같은 플랫폼에서 다른 호환 체크포인트 사용 |
| 실행 장치 | Windows의 `device`, `dtype`, `cpuThreads` | 음색 교체와 별개이며 설치기가 자동 선택 |

기본 `speaker_reference` 모드에서는 `speaker`나 `style`의 이름, `styles` 설명만 바꿔도 음색이 바뀌지 않는다. 실제 참조 WAV를 바꿔야 한다.

## 1. 서버 종료와 백업

먼저 통화를 끝낸다. 팝업의 **원래 목소리**는 탭만 원복하므로 서버 종료 명령도 실행한다.

Mac:

```sh
.tts-venv/bin/python src/voice_launcher.py --stop
mkdir -p artifacts/voice-backup
cp config/voice_settings.json artifacts/voice-backup/voice_settings.json
```

Windows PowerShell:

```powershell
& '.\.tts-venv\Scripts\python.exe' -X utf8 src/voice_launcher.py --stop
New-Item -ItemType Directory -Force artifacts/voice-backup | Out-Null
Copy-Item config/voice_settings.json artifacts/voice-backup/voice_settings.json
Copy-Item config/voice_settings.windows.json artifacts/voice-backup/voice_settings.windows.json
```

위 백업 경로는 이번 교체 전에 비어 있어야 한다. 이전 백업을 남겨야 한다면 새 폴더명을 사용한다. 기존 `voices/designed-soft.wav`와 모델 폴더는 그대로 두면 원복하기 쉽다.

## 2. 음색만 바꾸기

1. 사용할 참조 음성을 새 파일 `voices/my-voice.wav`로 둔다. 짧고 또렷한 단일 화자의 음성을 사용한다. 현재 앱의 참조 입력은 **24,000Hz·모노 WAV**로 준비한다. 엔진이 형식을 검사하며 스테레오·다른 샘플레이트를 자동 변환하지 않는다.
2. 파일의 SHA-256을 구한다.

   Mac:

   ```sh
   shasum -a 256 voices/my-voice.wav
   ```

   Windows:

   ```powershell
   (Get-FileHash voices/my-voice.wav -Algorithm SHA256).Hash.ToLowerInvariant()
   ```

3. 아래 **세 항목만** 설정 JSON에 반영한다. 전체 파일을 이 예제로 덮어쓰지 않는다. `<...>`는 실제 계산한 소문자 64자리 해시로 바꾼다.

   ```json
   {
     "mode": "speaker_reference",
     "referenceAudio": "voices/my-voice.wav",
     "referenceSha256": "<새 WAV의 SHA-256>"
   }
   ```

   - **Mac:** `config/voice_settings.json`을 수정한다.
   - **Windows:** `config/voice_settings.windows.json`을 수정한다. 4단계에서 설치기를 실행하면 이 템플릿에 장치 선택 결과를 더해 `config/voice_settings.json`을 다시 만든다. 실행 설정 파일만 수정하면 다음 설치 때 덮어써진다.

현재 참조 모드는 화자 특성만 사용하므로 참조 전사문을 추가할 필요가 없다. 원래 WAV가 손상돼 해시가 달라진 경우에는 해시만 맞추지 말고 원본을 복구한다. 위 절차는 의도적으로 새 참조 파일을 선택할 때 사용한다.

## 3. 합성 모델 바꾸기

음색만 바꾸려면 이 단계는 건너뛴다. **참조 음성 기반 Qwen3-TTS Base 모델** 안에서 플랫폼에 맞는 체크포인트를 고른다. Mac은 MLX 변환 모델, Windows는 공식 PyTorch 모델을 사용한다.

| 환경 | 기본 배포 모델 | 더 큰 Base 모델의 예 |
| --- | --- | --- |
| Mac | `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit` | `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit` |
| Windows | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` |

위 예는 해당 모델 형식을 보여준다. 이 앱의 고정 라이브러리 버전에서 모든 revision의 동작·음질·속도를 검증한 목록은 아니다. 모델을 키우면 메모리와 지연이 늘 수 있으므로 아래 합성 확인까지 수행한다. 모델 형식은 [MLX 모델 카드](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit)와 [공식 Base 모델 카드](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base)를 확인한다.

1. 선택한 모델의 전체 커밋 SHA를 확인해 `revision`으로 고정한다. Hugging Face 모델 페이지의 Files and versions에서 커밋을 확인하거나 다음처럼 조회한다. 조회는 메타데이터만 받는다.

   Mac 예:

   ```sh
   .tts-venv/bin/python -c "from huggingface_hub import HfApi; print(HfApi().model_info('mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit').sha)"
   ```

   Windows 예:

   ```powershell
   & '.\.tts-venv\Scripts\python.exe' -c "from huggingface_hub import HfApi; print(HfApi().model_info('Qwen/Qwen3-TTS-12Hz-1.7B-Base').sha)"
   ```

2. Mac은 `config/voice_settings.json`, Windows는 `config/voice_settings.windows.json`에서 아래 값을 함께 바꾼다. **기존 JSON의 나머지 항목과 참조 WAV 설정은 유지한다.**

   Mac 예:

   ```json
   {
     "backend": "mlx",
     "mode": "speaker_reference",
     "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit",
     "revision": "<위에서 확인한 전체 커밋 SHA>",
     "modelDirectory": "models/qwen3-tts-base-1.7b-4bit"
   }
   ```

   Windows 예:

   ```json
   {
     "backend": "torch",
     "mode": "speaker_reference",
     "model": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
     "revision": "<위에서 확인한 전체 커밋 SHA>",
     "modelDirectory": "models/qwen3-tts-base-1.7b"
   }
   ```

`modelDirectory`는 설치 폴더 기준 상대 경로다. 다른 모델이나 revision을 사용할 때는 **새 디렉터리**를 지정해 이전 가중치와 섞이지 않게 한다. 실제 추론은 이 로컬 디렉터리에서 모델을 읽으므로 `model` 이름만 바꾸고 다운로드를 생략하면 교체되지 않는다. 기존 모델의 SHA를 새 모델에 재사용하거나 `revision`을 `main`으로 두지 않는다.

### CustomVoice·VoiceDesign·다른 TTS 모델

Qwen의 Base·CustomVoice·VoiceDesign은 호출 API와 입력이 다르다. [공식 사용법](https://github.com/QwenLM/Qwen3-TTS#python-package-usage)을 참고한다. 이 프로젝트에서는 다음 범위를 구분한다.

- **Windows:** `src/tts_torch_engine.py`가 Base의 참조 음성 API를 호출한다. `mode`나 모델 이름만 바꿔 CustomVoice·VoiceDesign을 사용할 수 없다. 엔진의 초기화·합성 구현이 추가로 필요하다.
- **Mac:** `src/tts_bridge_server.py`에는 `voice_design`과 `custom_voice` 분기가 있다. 해당 MLX 모델과 API가 고정된 `mlx-audio` 버전에 맞아야 한다. VoiceDesign은 `styles[style]` 설명, CustomVoice는 모델이 지원하는 `speaker`와 스타일을 사용한다. 단순 Base 모델 교체 절차와 다르며, 직접 사용할 경우 워밍업·연속 합성·취소·실제 통화를 다시 확인한다.
- 다른 계열의 TTS 모델은 설정 이름만 바꿔 연결할 수 없다. 현재 엔진 인터페이스에 맞춘 오디오 출력·취소 처리가 필요하다.

일관된 새 캐릭터 음색이 목적이면 VoiceDesign 등으로 참조 WAV를 별도로 만든 뒤, 이 앱의 Base 참조 모드에서 2단계처럼 사용하는 방법이 있다. 이 문서는 참조 음성을 자동 생성하거나 기존 배포 WAV를 교체하지 않는다.

## 4. 적용과 확인

Mac:

```sh
python3.11 src/setup_chrome.py --no-open
.tts-venv/bin/python tools/check.py
```

Windows:

```powershell
py -3.11 -X utf8 src/setup_windows.py --no-open
& '.\.tts-venv\Scripts\python.exe' -X utf8 tools/check.py
```

설치기가 선택한 모델·revision을 내려받고 참조 해시를 확인한다. Windows는 장치·정밀도·스레드를 다시 선택하고 실제 합성 측정 결과를 `runtime/benchmark.json`과 `artifacts/windows-voice-test.wav`에 남긴다. 기본 설치기의 GPU 후보 조건은 더 큰 모델의 메모리 적합성을 보장하지 않는다.

1. 설치기가 확장 파일도 갱신하므로 Chrome 확장 카드에서 **새로고침**을 누른다.
2. dots 대화 탭에서 Dots Voice를 연결한다. 설정이 바뀐 서버가 남아 있다는 오류가 나면 해당 설치 폴더의 서버를 정상 종료한 뒤 다시 연결한다.
3. **목소리 듣기**로 음색을 확인하고, 새 통화에서 여러 문장의 답변과 발화 중단을 확인한다.

`tools/check.py`는 모델 없는 검사이므로 새 모델의 합성 성공을 증명하지 않는다. Mac의 실제 로딩·합성은 연결 및 미리듣기로, Windows는 설치 측정과 실제 Chrome 통화로 확인한다. 오류는 `runtime/tts-server.log`, Windows 측정 오류는 `runtime/setup-benchmark.log`를 본다. 임시 인증 정보인 `runtime/tts-bridge-config.json`은 공유하지 않는다.

## 5. 원래 설정으로 되돌리기

서버를 종료하고 1단계 백업을 복원한 뒤 4단계 설치·연결을 다시 진행한다.

Mac:

```sh
cp artifacts/voice-backup/voice_settings.json config/voice_settings.json
```

Windows:

```powershell
Copy-Item artifacts/voice-backup/voice_settings.json config/voice_settings.json
Copy-Item artifacts/voice-backup/voice_settings.windows.json config/voice_settings.windows.json
```

새 WAV와 새 모델 폴더는 남아 있어도 기존 설정에서 참조하지 않는다. 새 설치 ZIP으로 업데이트할 때에는 사용자 설정을 별도 백업한다. 설정·WAV를 변경한 뒤에는 배포 ZIP 내부의 원본 `SHA256SUMS.txt`와 해당 파일들이 달라지는 것이 정상이다.

직접 수정한 구성을 다시 배포하려면 소스 저장소에서 새 WAV와 출처를 패키지 허용 목록에 추가하고 커밋·빌드·검증한다. 원래 배포 ZIP의 체크섬 파일만 고쳐서 공식 릴리즈처럼 공유하지 않는다.
