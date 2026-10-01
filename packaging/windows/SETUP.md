# 설치·검증 절차 (Windows 11)

목표는 이 PC 사양에 맞춰 Chrome dots 통화에 포함된 **로컬 목소리**를 연결하는 것이다. 원본 사용자의 경로나 개발 환경을 복사하지 않는다. 모든 경로는 현재 압축 해제 폴더를 기준으로 정한다. 사용자에게 GPU 사양을 다시 묻기 전에 직접 확인한다.

## 사양 확인과 설치

1. Windows 11 x64, Chrome, 64비트 Python 3.11이 있는지 확인한다. `py -3.11 --version`을 사용한다. Python이 없으면 공식 Python 3.11 x64 설치 또는 `winget install --id Python.Python.3.11 --exact --source winget --accept-source-agreements --accept-package-agreements`로 설치한다. 관리자 승인 창이나 조직의 설치 승인 절차가 뜨면 사용자에게 맡긴다. 설치 직후에는 에이전트의 셸 PATH가 갱신되지 않아 `py`를 못 찾을 수 있다. 그때는 `%LOCALAPPDATA%\Programs\Python\Python311\python.exe`처럼 절대 경로로 확인하고 아래 `py -3.11` 대신 그 경로를 쓴다.
2. ZIP 전체를 쓰기 가능한 고정 폴더에 압축 해제한다. ZIP 내부에서 실행하지 않는다. 먼저 `Unblock-File`로 인터넷 다운로드 표시를 지운다. OneDrive와 동기화되는 바탕 화면·문서 대신 `%USERPROFILE%\Dots-Voice-Windows11` 같은 위치를 쓴다. `SHA256SUMS.txt`는 설치 전에만 전부 일치한다. 설치기가 `config/voice_settings.json`을 장치 선택에 맞게 다시 쓴다. 폴더를 나중에 옮기면 설치기를 다시 실행하고 확장을 새 위치에서 등록해야 한다.
3. `py -3.11 -X utf8 src/setup_windows.py --inspect`로 사양만 먼저 확인한다. 이 단계는 모델·패키지를 내려받지 않는다. `runtime/hardware.json`에 CPU, 물리 코어, RAM, GPU, VRAM, NVIDIA 드라이버/CUDA 지원, 디스크 여유가 기록된다. PowerShell/CIM 조회가 실패한 필드는 미확인으로 취급하고 필요하면 직접 확인한다.
4. `py -3.11 -X utf8 src/setup_windows.py --no-open`으로 설치한다. 일반 사용자는 `install-windows.cmd`를 더블클릭해도 된다. 관리자 권한을 기본 요구하지 않는다. 처음 설치할 때 수 GB를 내려받고 음성 측정을 최대 두 번(각 10분 제한) 하므로 오래 걸린다. 명령 실행 시간 제한이 짧으면 `Start-Process py -ArgumentList '-3.11 -X utf8 src/setup_windows.py --no-open' -RedirectStandardOutput setup.log -RedirectStandardError setup-error.log -WindowStyle Hidden`처럼 백그라운드로 실행하고, `setup.log`에 `설치 파일 준비 완료`가 나오거나 `setup-error.log`에 오류가 남을 때까지 확인한다.
5. 설치기는 전용 `.tts-venv`를 만들고 PyTorch 2.10.0 + torchaudio 2.10.0을 공식 CPU/cu128 인덱스에서 설치한다. NVIDIA VRAM 6 GiB 이상과 드라이버 CUDA 12.8 이상을 후보 조건으로 삼는다. PyTorch에서 실제 CUDA 연산, 사용 가능 메모리를 확인한 뒤 GPU와 bf16/fp16을 고른다. 사용할 수 없으면 CPU fp32로 설정한다. CPU 스레드는 물리 코어 수 기준 최대 8개다. AMD/Intel GPU는 CPU 경로를 사용한다.
6. `config/voice_settings.windows.json`의 원본 음색 설정에 장치 선택을 반영해 `config/voice_settings.json`을 만든다. 고정 모델 revision을 내려받고, Chrome 네이티브 호스트를 현재 사용자의 레지스트리에 등록한다. 짧은 워밍업과 음성 합성으로 지연을 측정한다. 모델 실행 중 CUDA 메모리가 부족하면 CPU로 한 번 다시 측정한다. 드라이버 변경·폴더 이동 시 재설치한다. 같은 폴더의 서버가 실행 중이면 먼저 종료한다. `install-windows.cmd`와 `stop-windows.cmd`는 사람용이라 마지막 `pause`에서 입력을 기다린다. 에이전트는 `py -3.11 -X utf8 src/setup_windows.py`와 `.\.tts-venv\Scripts\python.exe -X utf8 src/voice_launcher.py --stop`을 직접 실행한다.
7. 자동 선택을 바꿔야 할 때(예: 측정이 느린 GPU 대신 CPU)는 설치 후 `config/voice_settings.json`의 `device`(`cpu` 또는 `cuda:0` 등), `dtype`(`float32`/`bfloat16`/`float16`), `cpuThreads`만 고친다. 그다음 서버를 종료하고 팝업에서 다시 연결한다. 실행 중인 서버는 설정 변경을 감지하면 연결을 거부한다. 설치기를 다시 실행하면 자동 선택으로 돌아간다.

네이티브 호스트 등록 위치는 `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.dots.local_voice`이며 기본값은 `runtime/com.dots.local_voice.json`의 절대 경로다. 확장 ID는 `hfpnnbdannadjliefcahcocbnpapccic`이다. 확장 공개 키를 바꾸지 않는다.

설치기는 32비트·64비트 레지스트리 보기에 모두 현재 경로를 등록하고, 실제 `.cmd` 실행기로 모델 없는 ping을 보내 바이너리 응답을 검사한다. 결과는 `runtime/native-host-check.json`, Python 초기 실행 오류는 `runtime/native-host.log`에 저장한다. 이 검사는 Chrome의 접근 정책이나 실제 확장 연결까지 검증하지 않으므로 브라우저 확인도 필요하다.

## 연결과 실제 확인

사용자가 바로 등록할 수 있게 `explorer runtime\chrome-extension`으로 폴더를 열어 준다. Chrome 확장 프로그램 화면에서 개발자 모드를 켜고 **압축해제된 확장 프로그램 로드**로 `runtime/chrome-extension`을 선택한다. 새 확장은 도구 모음의 퍼즐 아이콘 메뉴 안에 들어가므로, 퍼즐 아이콘 → Dots Voice 옆 핀을 눌러 고정하도록 함께 안내한다. 이미 등록했다면 새로고침한다. 도구가 이 화면의 접근을 막으면 사용자가 이 단계만 수행하도록 안내한다. Chrome 프로필을 직접 수정하거나 다른 접근 경로로 우회하지 않는다.

실제 `https://chatgpt.com/dots/...` 대화 탭에서 Dots Voice 버튼을 누르고 연결 완료를 기다린다. 첫 서버 시작은 워밍업 때문에 오래 걸릴 수 있다. 연결 후 사용자에게 팝업의 **목소리 듣기**, 통화 시작, 몇 문장의 답변, 말을 시작했을 때 답변 중단, **원래 목소리** 복원을 차례로 확인해 달라고 요청한다. 에이전트는 소리를 들을 수 없으므로 들리는 결과는 사용자에게 확인을 요청하고 그 답을 그대로 보고한다. 새로고침한 탭에는 버튼을 다시 누른다. 기존 통화가 진행 중이었다면 끝낸 후 재연결한다. 사용자의 통화 계정과 마이크 허용은 해당 PC에서 처리한다.

진단 명령(PowerShell):

```powershell
& '.\.tts-venv\Scripts\python.exe' -X utf8 src/voice_launcher.py --status
& '.\.tts-venv\Scripts\python.exe' -X utf8 src/voice_launcher.py --stop
& '.\.tts-venv\Scripts\python.exe' -X utf8 tools/check.py
```

Node.js가 이미 있다면 `node tests/transcript_buffer.test.cjs`, `node tests/chrome_extension.test.cjs`도 실행한다. 실제 합성을 다시 측정하려면 서버를 종료한 후 가상환경 Python으로 `src/tts_diagnose.py`를 실행한다. 원래 통화와 동시에 별도 모델을 로딩하지 않는다.

- `runtime/hardware.json`: 선택한 장치와 선정 이유. GPU 이름만 보이는 것과 CUDA 연산 성공을 구분한다.
- `runtime/benchmark.json`: `ok`, `firstChunkMs`, `generationMs`, `generatedSeconds`, `realTimeFactor`. 생성 시간/음성 길이 비율이 1 이상이면 합성이 재생보다 느리다. 1 미만이어도 구절 전체가 완성돼야 첫 소리가 나므로 응답 지연은 남는다. 워밍업 후 고정 문장 한 번의 측정이며 실제 통화의 보장은 아니다.
- `artifacts/windows-voice-test.wav`: 고정 한국어 테스트 문장. `start artifacts\windows-voice-test.wav`로 열어 주고 음색·발음·공백은 사용자에게 확인을 요청한다.
- `runtime/setup-benchmark.log`, `runtime/tts-server.log`: 합성·시작 오류. `runtime/torch-probe.log`: PyTorch 장치 검사 실패 시 상세 오류. `runtime/installed-packages.txt`: 실제 설치 버전 기록. 의존성은 `requirements/requirements.windows.lock.txt`로 고정한다.

## 목소리와 연결 원리

`Qwen/Qwen3-TTS-12Hz-0.6B-Base`, revision `5d83992436eae1d760afd27aff78a71d676296fc`, `qwen-tts==0.1.1`을 사용한다. `voices/designed-soft.wav`는 원본에서 선택한 합성 캐릭터 참조음성이다. SHA256은 `835e8fd278a9d90d49edbe2cf221a589b1de348d9d084807af0740a9e8929e05`이며 설치 때 검증한다. `x_vector_only_mode=True`로 화자 특성을 추출해 캐시한다. Yui.pth나 RVC는 필요하지 않다.

Chrome 페이지의 WebRTC 데이터 채널에서 **assistant 출력 자막 이벤트**를 읽어 구절 단위로 로컬 TTS에 전달한다. 원래 오디오 패킷을 RVC로 변환하는 방식은 아니다. 로컬 서버가 합성한 PCM을 별도의 loopback WebRTC로 재생하고, 연결이 준비되면 원래 통화 음성을 음소거한다. 마이크와 dots 응답 생성은 기존 경로를 사용한다. 서버는 127.0.0.1:8766에서만 수신한다. 네이티브 호스트는 서버 시작과 SDP 연결만 담당하고, 대화 내용은 로컬 WebRTC 경로로 전달한다.

이 Windows 백엔드의 공식 API는 **구절 전체를 합성한 후 오디오를 반환**한다. `non_streaming_mode=False`도 실시간 PCM 스트리밍을 의미하지 않는다. 전송용 청크 분할을 스트리밍 추론이라고 설명하지 않는다. 생성 중 사용자 발화가 들어오면 talker의 다음 forward에서 이전 합성을 취소한다. Mac MLX 4bit와 모델 정밀도 및 구현이 달라 동일 WAV를 써도 결과 음색·운율·속도는 달라질 수 있다.

## 문제 해결

- **팝업의 `확장 프로그램을 새로고침해 주세요` 또는 `Unknown action`:** 설치기가 확장 파일을 바꿨지만 Chrome이 이전 background를 실행 중이다. 팝업의 새로고침 버튼이나 `chrome://extensions`의 Dots Voice 카드 새로고침을 누르게 한다.
- `Failed to construct 'URL'`: 설정 화면이 아니라 실제 dots 대화 탭으로 이동하고 확장을 새로고침한다. 이 패키지에는 빈 tab.url 방어 코드가 들어 있다.
- `Specified native messaging host not found`: 설치 폴더 이동 여부, 레지스트리 기본값, manifest 경로, 확장 ID를 확인하고 설치기를 다시 실행한다.
- `Native host has exited`: `runtime/native-host-check.json`과 `runtime/native-host.log`를 먼저 확인한다. Python 경로 소실·실행 실패와 Chrome 쪽 차단을 구분한다. 바이너리 입출력에는 진단 문구를 출력하지 않는다. 호스트 검사만 다시 실행하려면 가상환경 Python으로 `-c "import sys; sys.path.insert(0, 'src'); from setup_windows import check_native_host; check_native_host()"`를 실행한다. 보안 프로그램이나 조직 정책의 차단이면 해당 오류를 보고하고 보호 기능을 임의로 끄지 않는다.
- `torch` DLL 로드 오류: Python이 x64/3.11인지 확인한다. 오류가 요구하면 Microsoft 공식 Visual C++ x64 런타임을 설치한다. 설치 실패를 CPU 성능 문제로 취급하지 않는다.
- CUDA 실패/CPU 선택: 사양 결과와 실제 probe를 구분한다. 드라이버가 오래됐거나 GPU 여유 메모리가 적을 수 있다. 드라이버 설치를 무조건 자동 실행하지 않는다. CPU 사용 중 통화가 느리면 측정 수치를 제시하고 유료 API나 다른 목소리로 임의 변경하지 않는다.
- 8766 포트 충돌: 해당 프로세스가 이 폴더의 서버인지 확인한다. 다른 프로그램을 강제 종료하지 않는다.
- 음성 테스트 시간 초과: 10분 제한 결과를 보고 미검증으로 표시한다. `--skip-benchmark`는 문제 조사용이며 통과를 의미하지 않는다.

제작 환경은 Mac이다. 코드 검사·모의 Windows 레지스트리/락/장치 선택·오디오 버퍼 테스트를 했으며, 실제 Windows CUDA/CPU 합성, Chrome 등록과 통화는 이 PC에서 검증해야 한다. 설치 완료와 실제 통화 검증 완료를 구분해 보고한다.

공식 참고: [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), [고정 Base 모델](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base/tree/5d83992436eae1d760afd27aff78a71d676296fc), [PyTorch 설치](https://pytorch.org/get-started/locally/), [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging).
