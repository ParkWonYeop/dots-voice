# Dots Voice

**Chrome의 dot 통화 답변을 로컬 한국어 캐릭터 목소리로 듣는 도구입니다.**

답변 자막을 Qwen3-TTS로 합성하고, 포함된 고정 참조 음성으로 화자 특성을 유지합니다. Chrome 확장 버튼을 누르면 로컬 서버가 자동으로 시작됩니다. 마이크 입력과 답변 생성은 기존 ChatGPT 연결을 사용하며, 추가 음성 API 키는 필요하지 않습니다.

개인 프로젝트이며 OpenAI의 공식 제품이나 확장 프로그램이 아닙니다. 본인 계정에서 dots 웹 통화를 사용할 수 있어야 합니다.

> [!WARNING]
> 이 도구는 dots 통화의 답변 자막을 프로그램으로 읽어 로컬 음성으로 합성하므로, [OpenAI 이용약관](https://openai.com/policies/terms-of-use/)의 데이터·출력 자동 추출 금지 조항에 위배될 위험이 있습니다. 사용 전 관련 약관을 확인하세요. MIT 라이선스는 OpenAI 서비스 이용 허가를 의미하지 않습니다.

## 다운로드

| 환경 | 설치 ZIP | 상세 설치·문제 해결 |
| --- | --- | --- |
| Apple Silicon Mac · M1 이상 | [Dots-Voice-Mac.zip](https://github.com/ParkWonYeop/dots-voice/releases/latest/download/Dots-Voice-Mac.zip) | [Mac 안내](packaging/macos/SETUP.md) |
| Windows 11 · x64 | [Dots-Voice-Windows11.zip](https://github.com/ParkWonYeop/dots-voice/releases/latest/download/Dots-Voice-Windows11.zip) | [Windows 안내](packaging/windows/SETUP.md) |

[전체 릴리즈](https://github.com/ParkWonYeop/dots-voice/releases) · [ZIP SHA-256](https://github.com/ParkWonYeop/dots-voice/releases/latest/download/SHA256SUMS.txt)

**릴리즈의 운영체제별 ZIP을 받으세요.** GitHub가 자동으로 제공하는 `Source code (zip)`은 개발용 소스이며, 운영체제별 설정과 루트의 설치 프롬프트가 준비된 배포 ZIP과 다릅니다. 두 설치 ZIP에는 코드·Chrome 확장·참조 WAV·설치 지침·프롬프트가 들어 있고, Python 환경과 모델은 첫 설치 때 내려받습니다.

## 필요한 환경

| 항목 | Mac | Windows |
| --- | --- | --- |
| 운영체제·CPU | macOS, Apple Silicon arm64 | Windows 11, x64 |
| Python | 3.11 arm64 | 3.11 x64 |
| 브라우저 | Google Chrome | Google Chrome |
| 합성 방식 | MLX 0.6B Base 4bit, 스트리밍 | PyTorch 0.6B Base, 구절 전체 합성 후 재생 |
| 하드웨어 | M5 / 32GB에서 검증 | RAM 16GB·여유 디스크 20GB 권장 |
| 가속 | Apple GPU | NVIDIA VRAM 6GiB 이상·CUDA 12.8 지원 드라이버를 후보로 검사, 불가하면 CPU |

Intel Mac, Windows ARM, AMD/Intel GPU 가속, 모바일, ChatGPT 데스크톱 앱은 지원 범위 밖입니다. Windows CPU에서는 응답 지연이 클 수 있습니다. Windows 실기기 설치·합성·통화는 아직 검증되지 않았으며, 설치기가 해당 PC에서 사양 검사와 실제 합성 측정을 수행합니다. Mac과 Windows의 음색·속도가 완전히 같지는 않습니다.

## 방법 1 · 직접 설치

### Mac

1. 위 Mac ZIP을 받고 **홈 폴더 아래의 고정 위치**에 압축을 풉니다. 터미널에서:

   ```sh
   ditto -x -k ~/Downloads/Dots-Voice-Mac.zip ~/
   cd ~/Dots-Voice-Mac
   ```

2. Python 3.11을 준비합니다. Homebrew가 이미 설치돼 있다면 `brew install python@3.11`을 사용할 수 있습니다.
3. `install-mac.command`를 더블클릭합니다. 터미널에서는 다음 명령으로 설치할 수 있습니다.

   ```sh
   python3.11 src/setup_chrome.py
   ```

4. 아래 **Chrome 연결**을 진행합니다. 첫 설치에는 약 1.7GB의 모델과 Python 패키지 다운로드 시간이 필요합니다.

데스크탑·문서·다운로드 폴더는 macOS 파일 접근 제한에 걸릴 수 있어 설치 위치로 피합니다. 폴더를 옮겼다면 설치기를 다시 실행합니다. `.command`를 열 수 없다면 [Mac 오류 처리](packaging/macos/SETUP.md#오류-처리)를 확인하세요.

### Windows 11

1. 위 Windows ZIP을 받고 PowerShell에서 차단 해제 후 홈 폴더 아래에 압축을 풉니다.

   ```powershell
   Unblock-File "$env:USERPROFILE\Downloads\Dots-Voice-Windows11.zip"
   Expand-Archive "$env:USERPROFILE\Downloads\Dots-Voice-Windows11.zip" -DestinationPath $env:USERPROFILE
   Set-Location "$env:USERPROFILE\Dots-Voice-Windows11"
   ```

2. **Python 3.11 x64**를 준비합니다. `py -3.11 --version`으로 확인합니다.
3. `install-windows.cmd`를 더블클릭합니다. PowerShell에서는 다음 명령으로 설치할 수 있습니다.

   ```powershell
   py -3.11 -X utf8 src/setup_windows.py
   ```

4. CPU·RAM·GPU 검사, 의존성·모델 다운로드, 실제 합성 측정이 끝나면 아래 **Chrome 연결**을 진행합니다.

OneDrive와 동기화되는 바탕 화면·문서 폴더는 설치 위치로 피합니다. 설치 중 수 GB를 내려받으며 CPU 합성 측정은 오래 걸릴 수 있습니다. 결과는 `runtime/hardware.json`과 `runtime/benchmark.json`에 저장됩니다.

### Chrome 연결 · 두 운영체제 공통

1. Chrome 주소창에 `chrome://extensions`를 입력하고 **개발자 모드**를 켭니다.
2. **압축해제된 확장 프로그램 로드**를 누르고, 설치 폴더 안의 **`runtime/chrome-extension`**을 선택합니다. 저장소의 `chrome-extension` 원본 대신 설치기가 준비한 폴더를 사용하세요.
3. 도구 모음의 퍼즐 아이콘에서 **Dots Voice**를 고정합니다.
4. **dots 대화 탭으로 이동**해 Dots Voice 버튼을 누릅니다. 기존 통화는 먼저 끝냅니다.
5. **로컬 목소리 연결 완료**를 확인한 뒤 새 통화를 시작합니다. **소리를 켜 주세요**가 나오면 dots 페이지를 한 번 클릭합니다.

확장 등록은 처음 한 번 사용자가 직접 해야 합니다. 이후에는 새 통화 전에 확장 버튼만 누르면 서버가 자동으로 시작되거나 재사용됩니다. 페이지를 새로고침했으면 버튼을 다시 누릅니다.

## 방법 2 · ZIP과 프롬프트로 에이전트에게 설치 맡기기

1. 자신의 운영체제에 맞는 ZIP을 받습니다.
2. **설치할 컴퓨터에서 파일·터미널을 사용할 수 있는** Codex, Claude Code, Cursor 등의 에이전트에 ZIP 또는 압축 해제 폴더를 제공합니다.
3. ZIP 안의 **`AGENT_PROMPT.txt`** 내용을 복사해 보냅니다. 파일은 온라인에서도 볼 수 있습니다: [Mac 프롬프트](packaging/macos/AGENT_PROMPT.txt) · [Windows 프롬프트](packaging/windows/AGENT_PROMPT.txt).

공통으로 아래처럼 요청해도 됩니다.

```text
첨부한 Dots Voice ZIP을 이 컴퓨터에 설치하고 Chrome dots 통화에 연결해 줘.
압축을 홈 폴더 아래 고정 위치에 풀고, AGENTS.md를 먼저 읽은 뒤 SETUP.md를 따라 줘.
포함된 참조 목소리, 모델 revision, 확장 키는 유지해 줘.
Chrome 확장 등록처럼 내가 직접 해야 하는 단계는 클릭할 항목과 폴더 경로를 알려줘.
실제로 통과한 검사와 내가 아직 확인해야 할 것을 짧게 알려줘.
```

에이전트가 환경 검사·설치·진단을 맡습니다. Windows에서는 사양에 맞춰 장치와 정밀도를 선택하고 합성 속도를 측정합니다. Chrome 확장 등록과 실제 통화 청취 확인은 사용자가 합니다. 원격 웹 채팅만으로는 사용자 PC 설치가 완료되지 않으므로 위 수동 절차 또는 해당 PC의 로컬 에이전트를 사용하세요.

## 목소리·모델 교체

[목소리·모델 교체 안내](docs/VOICE_MODELS.md)에 플랫폼별 설정 파일, 참조 WAV·해시 변경, Base 모델 교체, 재설치·확인·원복 절차를 정리했습니다. 같은 안내가 설치 ZIP에도 들어 있습니다.

- **음색만 변경:** 새 참조 WAV의 `referenceAudio`와 `referenceSha256`을 설정합니다.
- **합성 모델 변경:** 해당 플랫폼의 호환 Base 모델로 `model`·`revision`·`modelDirectory`를 함께 바꿉니다.
- Windows는 설치할 때 `config/voice_settings.windows.json`에서 실행 설정을 다시 만듭니다. 템플릿도 수정해야 변경 내용이 유지됩니다.

## 사용·종료·업데이트

- **목소리 듣기:** 확장 팝업에서 미리듣기를 실행합니다.
- **원래 목소리:** 해당 탭의 음성 교체를 해제합니다. 서버는 다음 통화를 위해 남습니다.
- **서버 종료:** Mac은 `Dots Voice 종료.command`, Windows는 `stop-windows.cmd`를 실행합니다.
- **업데이트:** 통화와 기존 서버를 종료하고 새 릴리즈를 고정 폴더에 풉니다. 새 폴더에서 설치기를 실행하고 Chrome의 기존 확장을 새로고침합니다. 경로가 바뀌었다면 이전 확장을 제거한 뒤 새 `runtime/chrome-extension`을 등록합니다.
- **문제 진단:** [Mac](packaging/macos/SETUP.md#오류-처리) · [Windows](packaging/windows/SETUP.md#문제-해결). `runtime/tts-server.log`를 먼저 확인하고, 인증 토큰이 들어 있는 `runtime/tts-bridge-config.json`은 공유하지 마세요.

## 구조와 개발

```text
chrome-extension/  Chrome 팝업, 연결 제어, 자막·오디오 후크
src/               설치기, 네이티브 실행기, TTS 서버·오디오 처리
config/            고정 음색·모델 설정과 합성 샘플 출처
voices/            배포에 사용하는 참조 WAV와 출처
requirements/      플랫폼별 Python 의존성 고정 파일
tests/             모델을 로딩하지 않는 Python·JavaScript 검사
tools/             검사, ZIP 제작·검증, 수동 연결·비교 도구
packaging/         Mac·Windows ZIP에 들어갈 README·지침·프롬프트
docs/              개발·구조·기존 측정 기록
experiments/rvc/   초기 RVC 실험 보관본; 설치 ZIP에는 포함하지 않음
```

설치 후 생기는 `.tts-venv/`, `models/`, `runtime/`, `artifacts/`는 Git과 배포 ZIP에서 제외합니다. 루트의 `voice_launcher.py`는 이전 Mac 설치기의 경로를 유지하는 호환 진입점입니다.

[개발·검사·릴리즈](docs/DEVELOPMENT.md) · [연결 구조](docs/ARCHITECTURE.md) · [기존 측정과 한계](docs/MEASUREMENTS.md) · [변경 기록](CHANGELOG.md)

## 처리 범위와 출처

통화 답변 자막과 합성 음성은 브라우저와 로컬 서버 사이의 WebRTC로 오갑니다. 서버는 `127.0.0.1:8766`에서만 수신하며 확장은 `activeTab`, `scripting`, `nativeMessaging` 권한을 사용합니다. 이 도구는 마이크 녹음을 저장하지 않습니다. 첫 설치의 패키지·모델 다운로드 및 기존 ChatGPT 통화에는 인터넷 연결이 필요합니다.

[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) · [MLX Audio](https://github.com/Blaizzy/mlx-audio) · [Mac 모델](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit) · [Windows 모델](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base)

참조 WAV는 VoiceDesign으로 생성한 합성 캐릭터 음성입니다. 출처는 `voices/designed-soft.json`과 `config/voice_candidates.json`에 기록돼 있습니다. 모델과 라이브러리는 각 배포처의 라이선스 조건을 따릅니다. dots의 페이지 구조가 바뀌면 연결 코드의 수정이 필요할 수 있습니다.

## 라이선스

프로젝트의 자체 코드·문서·설정·리소스는 [MIT License](LICENSE)를 따릅니다. 저작권·라이선스 고지를 유지하면 상업적 사용, 수정, 재배포가 가능합니다. 외부 모델·라이브러리와 포함된 합성 참조 음성의 적용 범위는 [라이선스·출처 안내](THIRD_PARTY_NOTICES.md)를 확인하세요. 두 설치 ZIP에도 이 파일들을 포함합니다.
