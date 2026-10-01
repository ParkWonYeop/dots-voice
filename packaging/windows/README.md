# Dots Voice · Windows 11 설치 패키지

Chrome의 dots 통화 답변을 포함된 로컬 캐릭터 목소리로 읽게 하는 로컬 도구입니다.

> **AI 에이전트라면:** `AGENTS.md`를 먼저 읽고 `SETUP.md` 순서대로 진행한다.

## 에이전트에게 맡기기 (권장)

Codex, Claude Code, Cursor처럼 **내 PC에서 명령을 실행할 수 있는 에이전트**에 이 ZIP 파일(또는 압축을 푼 폴더)을 주고 `AGENT_PROMPT.txt`의 내용을 그대로 보내세요. 에이전트가 CPU·메모리·GPU를 확인해 알맞게 설치하고 실제 합성 속도를 측정합니다. Chrome 확장 등록처럼 사람이 직접 해야 하는 단계만 알려줍니다. 명령을 실행할 수 없는 웹 채팅에서는 아래 **직접 설치**를 따르세요.

## 직접 설치

1. ZIP 파일 속성에서 **차단 해제**를 체크한 뒤, OneDrive 동기화 밖의 고정 폴더(예: `%USERPROFILE%\Dots-Voice-Windows11`)에 압축을 풉니다. 설치 후 폴더를 옮기면 다시 설치해야 합니다.
2. **Python 3.11 x64**를 설치한 뒤 `install-windows.cmd`를 실행합니다. 설치기가 사양을 확인하고 CUDA 또는 CPU를 선택합니다.
3. Chrome 주소창에 `chrome://extensions`를 입력하고 개발자 모드를 켠 뒤 **압축해제된 확장 프로그램 로드**로 이 폴더 안의 `runtime\chrome-extension`을 선택합니다. 도구 모음의 퍼즐 아이콘을 눌러 Dots Voice를 고정(핀)하면 버튼이 보입니다.
4. 실제 dots 대화 탭에서 **Dots Voice → 로컬 목소리 연결 완료 → 통화 시작** 순서로 사용합니다. 팝업에 연결 단계가 표시되고, 아이콘 배지 `ON`은 연결됨, `클릭`은 dots 페이지를 한 번 클릭하라는 뜻, `!`는 오류입니다. 종료는 `stop-windows.cmd`입니다.

원본과 같은 `voices/designed-soft.wav`가 들어 있습니다. 모델은 Windows용 **Qwen/Qwen3-TTS-12Hz-0.6B-Base**이며 설치 중 내려받습니다. MLX 4bit를 쓰는 Mac과 정밀도·실행 방식이 달라 소리가 완전히 일치하지는 않습니다. 이 Windows 버전은 구절 전체를 합성한 뒤 재생하므로 Mac 스트리밍 버전보다 첫 소리와 문장 사이 지연이 늘 수 있습니다. NVIDIA GPU가 없으면 CPU로 실행하며 실시간 성능은 보장되지 않습니다.

Windows 11 x64와 Chrome용입니다. ARM Windows, AMD/Intel GPU 가속, ChatGPT 데스크톱 앱은 이 설치기의 지원 범위 밖입니다. RAM 16 GB 이상, 여유 디스크 20 GB 이상을 권장합니다. GPU 경로는 VRAM 6 GiB 이상·CUDA 12.8 지원 드라이버를 기준으로 실제 연산과 모델 합성을 확인합니다.

자동 설정 결과는 `runtime/hardware.json`, 합성 지연은 `runtime/benchmark.json`, 미리듣기는 `artifacts/windows-voice-test.wav`에 저장됩니다. 사양과 테스트 결과는 로컬에만 기록됩니다. 계정·쿠키·API 키는 포함되어 있지 않습니다.

이 패키지는 Mac에서 코드와 모의 Windows 경로를 검증해 만들었습니다. Windows 실기기 설치·합성·Chrome 통화는 받는 PC에서 확인해야 합니다.

## 목소리·모델 교체

ZIP 안의 `docs/VOICE_MODELS.md`를 따른다. 참조 WAV와 SHA-256을 바꾸는 음색 교체, 플랫폼에 맞는 Base 모델·revision·저장 폴더를 바꾸는 모델 교체, 재시작·확인·원복 절차를 설명한다. GitHub에서 읽는 경우 [온라인 안내](https://github.com/ParkWonYeop/dots-voice/blob/main/docs/VOICE_MODELS.md)를 사용한다.

## 라이선스

Dots Voice의 자체 코드·문서·설정·리소스는 MIT License를 따릅니다. 전문은 ZIP 루트의 `LICENSE`에 있습니다. 외부 모델·라이브러리는 원래 라이선스를 유지하며, 합성 참조 음성의 적용 범위와 구성 요소 출처는 `THIRD_PARTY_NOTICES.md`에 정리했습니다.
