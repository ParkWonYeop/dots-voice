# Dots Voice 설치 작업 지침 (Windows 11)

이 폴더는 Chrome dots 통화의 답변 음성을 포함된 **2번 목소리**로 바꾸는 로컬 도구의 Windows 설치 패키지다. 사용자가 설치·연결·진단을 맡기면 이 파일과 `SETUP.md`를 따른다. 원본 사용자의 경로가 아니라 **현재 패키지 폴더**를 기준으로 작업한다.

## 시작 전

- 사용자 컴퓨터에서 명령을 실행할 수 없는 환경(웹 채팅 등)이면 설치했다고 하지 않는다. `README.md`의 **직접 설치** 절차를 사용자에게 안내한다.
- ZIP 상태로 받았다면 차단 해제 후 OneDrive 동기화 밖의 고정 폴더에 푼다(PowerShell):
  `Unblock-File .\Dots-Voice-Windows11.zip; Expand-Archive .\Dots-Voice-Windows11.zip -DestinationPath $env:USERPROFILE` → `%USERPROFILE%\Dots-Voice-Windows11`. 바탕 화면·문서가 OneDrive와 동기화되면 수 GB의 모델과 가상환경까지 업로드되므로 피한다. 설치 후 폴더를 옮기면 다시 설치해야 한다.
- 지원 환경은 Windows 11 x64, 64비트 Python 3.11, Google Chrome이다. ARM Windows면 지원하지 않는다고 알리고 설치 성공으로 보고하지 않는다. Mac이면 `Dots-Voice-Mac.zip` 패키지가 필요하다고 알린다.

## 지킬 것

- 사용자에게 GPU 모델을 묻기 전에 CPU·RAM·GPU·VRAM·드라이버를 직접 확인한다. 장치·dtype·CPU 스레드만 사양에 맞게 조정한다(방법은 `SETUP.md` 7단계).
- 포함된 `voices/designed-soft.wav`, 모델 ID·revision, 음색 설정, 확장 공개 키(`manifest.json`의 `key`)를 바꾸지 않는다. Mac용 MLX 의존성을 설치하지 않는다.
- 합성이 느리면 수치를 보고한다. 동의 없이 유료 클라우드나 다른 목소리로 바꾸지 않는다.
- 설치 전에 실행 중인 서버를 확인하고 모델을 여러 프로세스에 중복 로딩하지 않는다. 8766 포트를 쓰는 관계없는 프로그램을 강제 종료하지 않는다.
- `chrome://extensions` 같은 Chrome 설정 화면이나 Chrome 프로필을 자동화·우회해서 조작하지 않는다. 확장 등록·새로고침은 사용자가 한다. 보안 프로그램이나 조직 정책을 끄지 않는다.

## 순서

1. `SETUP.md`의 사양 확인과 설치를 진행하고(오래 걸리므로 필요하면 백그라운드로 실행한다. 사람용 `.cmd`는 `pause`에서 멈추므로 쓰지 않는다) `runtime/hardware.json`, `runtime/benchmark.json`, `artifacts/windows-voice-test.wav`를 확인한다.
2. 사용자에게 Chrome 확장 등록을 안내한다. 클릭할 항목, 선택할 폴더의 **절대 경로**, 퍼즐 아이콘에서 Dots Voice를 고정하는 방법을 알려주고 완료했다는 답을 기다린다.
3. 사용자가 dots 대화 탭에서 도구 모음의 Dots Voice 버튼을 누르게 하고 팝업 문구를 묻는다. `2번 목소리 연결 완료`가 목표다. 팝업이 `확장 프로그램을 새로고침해 주세요`면 팝업 버튼이나 확장 카드의 새로고침을 누르게 한다.
4. 사용자에게 팝업의 **목소리 듣기**, 통화 중 답변, 말을 시작했을 때 중단, **원래 목소리** 복원을 확인해 달라고 요청한다. 에이전트가 직접 들었다고 보고하지 않는다. 모의 테스트나 WAV 생성만으로 실제 통화 검증을 완료했다고 하지 않는다.

## 완료 보고

설치 위치, 선택한 장치와 이유, 측정한 첫 소리·생성 속도, 실제로 통과한 검사, Chrome 등록 여부, 실제 통화 확인 여부(사용자가 확인했는지 포함), 사용자가 할 다음 동작만 짧게 보고한다. Windows 합성 결과가 Mac MLX 4bit와 같은 음색·지연이라고 보장하지 않는다.
