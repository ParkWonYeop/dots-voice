# 설치·검증 절차 (macOS)

이 지침은 사용자가 설치를 요청한 경우에 적용한다. 작업 폴더를 이 파일이 있는 압축 해제 폴더로 설정한다. `src/setup_chrome.py`는 현재 경로를 기준으로 설치하므로 원본 사용자의 디렉터리나 계정 정보가 필요하지 않다.

## 1. 환경과 파일 확인

```sh
uname -s
uname -m
command -v python3.11
python3.11 --version
shasum -a 256 -c SHA256SUMS.txt
python3.11 src/voice_launcher.py --status   # 표준 라이브러리만 사용. 이미 실행 중인 서버 확인
```

지원 환경은 Darwin / arm64 / Python 3.11이다. Python이 없고 Homebrew가 설치돼 있다면 `brew install python@3.11`로 준비한다. Homebrew가 없으면 사용자의 도구 설치 정책에 따라 공식 Python 3.11 배포판 또는 Homebrew를 준비한다. 관리자 암호가 필요한 설치(python.org `.pkg`, Homebrew 최초 설치)는 사용자에게 실행을 맡긴다. Google Chrome과 사용자의 dots 통화 접근 권한도 확인한다. ChatGPT 로그인은 사용자의 계정으로 진행하며 이 패키지는 계정을 제공하지 않는다.

확인할 고정 값:

| 항목 | 값 |
| --- | --- |
| 모델 | `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit` |
| revision | `0d6bb6fe33f92d47a507e23b9148940e8366ab5b` |
| 음성 모드 | `speaker_reference` |
| 참조 | `voices/designed-soft.wav` |
| 참조 SHA-256 | `835e8fd278a9d90d49edbe2cf221a589b1de348d9d084807af0740a9e8929e05` |
| 라이브러리 | `mlx-audio==0.5.7`, 전체 버전은 `requirements/requirements.tts.lock.txt` |

`config/voice_candidates.json`은 합성 샘플의 출처 기록이다. 다른 후보 모델을 받거나 새 목소리를 생성할 필요는 없다. 화자 참조에는 `ref_audio`만 사용하며 `ref_text`를 임의로 추가하지 않는다.

## 2. 로컬 설치

```sh
python3.11 src/setup_chrome.py --no-open
```

처음 설치는 약 1.7 GB 모델과 Python 패키지를 내려받아 오래 걸린다. 명령 실행 시간 제한이 짧으면 `nohup python3.11 src/setup_chrome.py --no-open > setup.log 2>&1 &`로 실행하고 `setup.log`에 `설치 파일 준비 완료`가 나올 때까지 확인한다.

이 명령은 `.tts-venv` 생성, 고정 의존성 설치, 고정 revision 모델 다운로드, 참조 WAV 확인, `runtime/chrome-extension` 생성, Chrome Native Messaging 호스트 등록을 처리한다. 별도 모델 비교 합성은 실행하지 않는다.

설치되는 호스트 파일은 사용자 홈 아래 `Library/Application Support/Google/Chrome/NativeMessagingHosts/com.dots.local_voice.json`이다. 이 패키지의 확장 ID 하나만 허용한다. 모델은 `config/voice_settings.json`의 상대 경로 `models/qwen3-tts-base-0.6b-4bit`에 저장한다. 처음 설치할 때 다운로드 시간이 걸린다.

Chrome이 직접 시작하는 실행 파일은 `~/Library/Application Support/Dots Voice/chrome-voice-host`에 둔다. 프로젝트의 Documents 경로에 시작 스크립트를 두면 Chrome에서 실행하기 전에 종료될 수 있다. 초기 실행 오류는 같은 폴더의 `native-host.log`에 기록한다.

셸에서 검사·설치할 때는 위 Python 명령이 적합하다. Finder에서 실행할 때는 `Dots Voice 설치.command`를 사용할 수 있다. 압축 해제 도구가 실행 권한을 잃었다면 다음 명령으로 복구한다.

```sh
chmod +x 'Dots Voice 설치.command' 'Dots Voice 종료.command'
```

## 3. Chrome에 등록

사용자가 바로 등록할 수 있게 `open runtime/chrome-extension`과 `open -a 'Google Chrome' 'chrome://extensions'`로 폴더와 확장 화면을 열어 준다. 사용자에게 `chrome://extensions`에서 개발자 모드를 켜고 **압축해제된 확장 프로그램 로드**로 현재 폴더의 `runtime/chrome-extension`을 선택하도록 안내한다. 새 확장은 도구 모음의 퍼즐 아이콘 메뉴 안에 들어가므로, 퍼즐 아이콘 → Dots Voice 옆 핀을 눌러 고정하도록 함께 안내한다. 이미 등록돼 있으면 Dots Voice 카드의 새로고침 버튼을 누른다. 설치기는 확장과 후크를 `runtime/chrome-extension`에 함께 준비한다. 설치·업데이트 절차와 일치하도록 로드 대상은 **runtime 아래 폴더**로 통일한다.

등록 후 실제 `https://chatgpt.com/dots/...` 대화 탭으로 이동한다. 기존 통화가 종료된 상태에서 도구 모음의 Dots Voice 버튼을 누른다. 완료되면 새 통화를 시작한다. 확장은 `activeTab`, `scripting`, `nativeMessaging`만 사용하므로 설정·확장 관리 화면에서 실행하면 dots 탭으로 이동하라는 안내가 나온다.

## 4. 검증

모델을 추가로 로딩하지 않는 검사:

```sh
.tts-venv/bin/python tools/check.py
```

Node.js가 이미 있으면 확장·자막 처리도 검사한다. 실행 자체에 Node.js는 필요 없다.

```sh
node tests/chrome_extension.test.cjs
node tests/transcript_buffer.test.cjs
node --check chrome-extension/dots-tts.js
```

서버 실행/상태 확인은 다음과 같다. 이미 실행 중인 서버는 재사용한다.

```sh
.tts-venv/bin/python src/voice_launcher.py
.tts-venv/bin/python src/voice_launcher.py --status
```

서버 시작은 모델 로딩·워밍업을 포함한다. 팝업은 서버 준비 → dots 페이지 연결 → 2번 목소리 연결 단계를 표시한다. `2번 목소리 연결 완료`를 확인한다. `소리를 켜 주세요`가 나오면 dots 페이지를 한 번 클릭한다. 사용자에게 새 통화에서 2번 목소리가 들리는지, 원음과 겹치지 않는지, 말을 시작했을 때 재생이 멈추는지 확인해 달라고 요청한다. 에이전트는 소리를 들을 수 없으므로 들리는 결과는 사용자에게 확인을 요청하고 그 답을 그대로 보고한다. 서버 준비만으로 실제 브라우저 출력까지 검증됐다고 보고하지 않는다.

종료:

```sh
.tts-venv/bin/python src/voice_launcher.py --stop
```

## 오류 처리

- **설치 `.command`를 열 수 없음:** 터미널에서 압축 해제 폴더로 이동한 뒤 `zsh 'Dots Voice 설치.command'` 또는 `python3.11 src/setup_chrome.py`를 실행한다. 보안 설정을 임의로 해제하지 않는다.
- **Python·패키지 설치 실패:** 정확한 오류와 macOS/Python 아키텍처를 확인한다. 잠금 파일을 임의로 최신 버전으로 바꾸지 않는다.
- **로컬 실행기를 찾지 못함:** 설치기를 다시 실행해 현재 폴더 경로로 호스트를 등록하고, 빌드된 확장을 새로고침한다.
- **Native host has exited:** 갱신된 설치기를 실행해 앱 데이터 폴더의 실행기로 다시 등록한다. 계속 실패하면 `~/Library/Application Support/Dots Voice/native-host.log`를 확인한다. 파일 접근 거부라면 사용자가 macOS의 파일 및 폴더 권한을 확인하도록 안내한다. 권한 설정을 우회하거나 전체 디스크 접근을 임의로 부여하지 않는다.
- **8766 포트 사용 중:** 어떤 프로세스인지 먼저 확인한다. 관계없는 서비스를 종료하지 않는다. 이전 수동 TTS 서버라면 해당 실행 터미널에서 종료한다.
- **다른 프로젝트 폴더의 서버:** 그 폴더에서 정상 종료한 뒤 새 폴더의 실행기를 사용한다.
- **참조 해시 불일치:** 동봉된 원래 WAV를 복원한다. 음성을 맞추는 작업에서 해시만 새 파일에 맞춰 변경하지 않는다.
- **팝업의 `확장 프로그램을 새로고침해 주세요` 또는 `Unknown action`:** 설치기가 확장 파일을 바꿨지만 Chrome이 이전 background를 실행 중이다. 팝업의 새로고침 버튼이나 `chrome://extensions`의 Dots Voice 카드 새로고침을 누르게 한다.
- **새로고침 후 원래 목소리:** 새 통화 전에 dots 탭에서 확장 버튼을 다시 누른다.
- **설정 변경 감지:** 서버를 정상 종료한 뒤 다시 연결한다.
- **시작 실패:** `runtime/tts-server.log`를 확인한다. `runtime/tts-bridge-config.json`에는 임시 인증 토큰이 있으므로 로그 공유물이나 배포물에 포함하지 않는다.
- **끊김/지연:** 동시에 실행 중인 다른 음성 모델 작업이 있는지 확인한다. 기존 무음 보정과 버퍼 설정을 유지하고, 필요하면 측정 후 별도 개선한다.

설치가 끝나면 설치 위치, 실제로 통과한 검사, Chrome 등록 여부, 실제 통화 확인 여부, 사용자가 해야 할 다음 동작만 간결하게 보고한다.
