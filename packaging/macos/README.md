# Dots Voice · Mac 설치 패키지

Chrome의 dots 통화 답변을 포함된 로컬 캐릭터 목소리로 읽게 하는 로컬 도구다.

> **AI 에이전트라면:** `AGENTS.md`를 먼저 읽고 `SETUP.md` 순서대로 진행한다.

## 에이전트에게 맡기기 (권장)

Codex, Claude Code, Cursor처럼 **내 컴퓨터에서 명령을 실행할 수 있는 에이전트**에 이 ZIP 파일(또는 압축을 푼 폴더)을 주고 `AGENT_PROMPT.txt`의 내용을 그대로 보낸다. 에이전트가 설치·검사를 진행하고, Chrome 확장 등록처럼 사람이 직접 해야 하는 단계만 알려준다. 명령을 실행할 수 없는 웹 채팅에서는 아래 **직접 설치**를 따른다.

## 필요한 환경

- Apple Silicon Mac(M1 이상), arm64 Python 3.11, Google Chrome.
- 본인 ChatGPT 계정에 dots 통화 기능이 있어야 한다.
- 첫 설치에는 인터넷 연결과 모델·Python 패키지용 저장 공간이 필요하다. 모델 가중치만 약 1.7GB이며 설치 환경은 추가 공간을 사용한다.
- 기존 검증 환경은 M5 / 메모리 32GB다. 다른 기기의 지연·끊김 정도는 달라질 수 있다. Intel Mac은 지원하지 않는다. Windows 11은 별도 패키지 `Dots-Voice-Windows11.zip`을 사용한다.

## 직접 설치

1. 압축을 풀어 홈 폴더 아래(예: `~/Dots-Voice-Mac`)처럼 계속 보관할 위치에 둔다. 데스크탑·문서·다운로드 폴더는 macOS 개인정보 보호 때문에 Chrome이 실행기를 시작하지 못할 수 있다. 설치 후 폴더를 옮겼다면 설치기를 다시 실행한다.
2. Python 3.11이 준비된 상태에서 `install-mac.command`를 더블클릭한다. Homebrew가 이미 있다면 Python 설치 명령은 `brew install python@3.11`이다. ‘확인되지 않은 개발자’ 경고로 열리지 않으면 **시스템 설정 → 개인정보 보호 및 보안 → 그래도 열기**를 누르거나, 터미널에서 이 폴더로 이동해 `zsh 'install-mac.command'`를 실행한다.
3. Chrome 주소창에 `chrome://extensions`를 입력한다. 개발자 모드를 켜고 **압축해제된 확장 프로그램 로드**에서 이 폴더 안의 `runtime/chrome-extension`을 선택한다. 도구 모음의 퍼즐 아이콘을 눌러 Dots Voice를 고정(핀)하면 버튼이 보인다.
4. **실제 dots 대화 탭으로 이동한 뒤** 도구 모음의 Dots Voice 버튼을 누른다. 확장 관리 화면에서는 실행하지 않는다.
5. 팝업에 연결 단계가 표시된다. **로컬 목소리 연결 완료**를 확인하고 새 통화를 시작한다. **소리를 켜 주세요**가 나오면 dots 페이지를 한 번 클릭한다. 아이콘 배지 `ON`은 연결됨, `클릭`은 페이지 클릭 필요, `!`는 오류다.

다음부터는 새 통화 전에 Dots Voice 버튼만 누른다. 로컬 서버는 자동 실행되고 이미 켜져 있으면 재사용한다. 페이지를 새로고침했으면 버튼을 다시 누른다. 팝업의 **원래 목소리**는 해당 탭의 후크를 제거한다. 서버까지 끄려면 `Dots Voice 종료.command`를 실행한다.

## 같은 목소리가 유지되는 조건

`voices/designed-soft.wav`는 원래 사용자가 고른 합성 음성 샘플(24kHz 모노, 11.76초)이다. `config/voice_settings.json`과 함께 그대로 사용해야 한다. VoiceDesign으로 샘플을 다시 생성할 필요는 없다.

통화 모델은 `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit`이며, 모델 revision과 Python 패키지 버전도 고정했다. `speaker_reference` 모드에서 참조 WAV의 화자 특성을 사용한다. 문장과 실행 환경에 따라 억양은 달라질 수 있다. 현재 모드에서는 `styles`의 설명을 수정해도 합성에 반영되지 않는다.

## 포함 범위와 동작

코드, Chrome 확장, 고정 설정, 선택한 합성 음성, 자동 검사, 설치 지침을 포함한다. 원래 사용자의 계정·쿠키·대화·로그·인증 토큰·다운로드한 모델·가상환경은 포함하지 않는다. 설치기는 이 컴퓨터에 맞는 경로와 로컬 실행기 등록을 새로 만든다. 설치 후 폴더 위치를 유지한다.

Chrome에서 WebRTC 데이터 채널의 답변 자막을 받아 로컬 Qwen3-TTS로 합성한다. 별도 로컬 WebRTC 연결로 음성을 돌려받아 재생하고 dots 원음을 음소거한다. 마이크 입력과 dots 답변 생성은 기존 ChatGPT 연결을 사용한다. 추가 음성 합성 API 키는 필요 없다. 이 도구는 마이크 녹음을 저장하지 않는다.

기존 Chrome 수동 후크 통화와 로컬 서버 자동 실행·재사용·종료·WebRTC 연결, 확장 제어 로직은 검사했다. 이 배포본의 Chrome 확장 버튼부터 통화까지의 전체 경로는 받는 컴퓨터에서 최종 확인해야 한다. 서비스의 페이지 구현이 바뀌면 후크 조정이 필요할 수 있다.

설치 문제가 나면 에이전트에게 `SETUP.md`의 오류 처리를 따라 진단해 달라고 요청한다. 포함 파일의 SHA-256은 `SHA256SUMS.txt`, 배포 정보는 `PACKAGE_INFO.json`에 있다.

모델·라이브러리 출처: [MLX 모델](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit), [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), [MLX Audio](https://github.com/Blaizzy/mlx-audio). 모델과 의존성은 각 배포처의 라이선스 조건을 따른다.

## 목소리·모델 교체

ZIP 안의 `docs/VOICE_MODELS.md`를 따른다. 참조 WAV와 SHA-256을 바꾸는 음색 교체, 플랫폼에 맞는 Base 모델·revision·저장 폴더를 바꾸는 모델 교체, 재시작·확인·원복 절차를 설명한다. GitHub에서 읽는 경우 [온라인 안내](https://github.com/ParkWonYeop/dots-voice/blob/main/docs/VOICE_MODELS.md)를 사용한다.

## 라이선스

Dots Voice의 자체 코드·문서·설정·리소스는 MIT License를 따른다. 전문은 ZIP 루트의 `LICENSE`에 있다. 외부 모델·라이브러리는 원래 라이선스를 유지하며, 합성 참조 음성의 적용 범위와 구성 요소 출처는 `THIRD_PARTY_NOTICES.md`에 정리했다.
