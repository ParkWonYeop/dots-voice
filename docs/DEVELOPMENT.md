# 개발·검사·릴리즈

일반 설치는 루트 README의 운영체제별 릴리즈 ZIP을 사용한다. 개발용 clone에는 두 운영체제의 소스와 이전 실험이 함께 들어 있다.

## 개발 환경

Python 3.11과 Node.js가 필요하다. Node.js는 확장 검사에만 사용한다. Mac의 전체 실행 환경은 `python3.11 src/setup_chrome.py --no-open`, Windows는 `py -3.11 -X utf8 src/setup_windows.py --no-open`으로 준비한다. 설치기는 모델 다운로드와 사용자별 Chrome 호스트 등록을 수행한다.

모델과 Chrome 등록 없이 검사만 하려면 별도 가상환경에서 최소 의존성을 설치한다.

```sh
python3.11 -m venv .venv
# Mac/Linux: .venv/bin/python / Windows: .venv\Scripts\python.exe
.venv/bin/python -m pip install -r requirements/test.txt
.venv/bin/python tools/check.py
```

이미 설치한 환경에서는 Mac의 `.tts-venv/bin/python tools/check.py`, Windows의 `.\.tts-venv\Scripts\python.exe -X utf8 tools/check.py`를 사용한다. 검사기는 `src/`를 Python 경로에 추가하고 Python 단위 검사, 오디오·프로세스 검사, JavaScript 검사, 구문 검사를 실행한다. Node.js가 없으면 JavaScript는 생략됐다고 표시한다. 릴리즈 전에는 Node.js를 준비해 모두 실행한다.

검사 범위는 메시지 프레이밍, 잘못된 확장·서버 거부, 서버 재사용, Mac 실제 네이티브 실행기, 모의 Windows 등록·장치 선택, CUDA 실패 후 CPU 복구, PCM 리샘플링·무음 보정·취소, 확장 연결·자막 처리다. 실제 모델의 음질·속도, Windows 드라이버·Chrome 정책, 사용자 계정의 dots 통화 성공은 별도 확인해야 한다.

## 설정과 파일 경로

- `config/voice_settings.json`: 현재 실행 설정. Windows 설치기는 원본 `config/voice_settings.windows.json`에 장치·정밀도·스레드 설정을 적용해 이 파일을 쓴다.
- `voices/designed-soft.wav`: 고정 참조 음성. 설치·패키징 시 SHA-256을 확인한다.
- `chrome-extension/manifest.json`: 확장 버전과 공개 키. 공개 키가 바뀌면 확장 ID와 호스트 허용 대상이 바뀌므로 유지한다.
- 소스의 `ROOT`는 파일 위치 기준 저장소/패키지 루트다. 설치기는 작업 디렉터리에 의존하지 않고 상대 모델·참조 경로를 이 루트에서 해석한다.
- `runtime/tts-bridge-config.json`은 실행 때 생성되는 인증 정보다. 저장소·배포물·이슈에 넣지 않는다.

Windows 설치 후 바뀐 실행 설정은 개인 PC용이다. 릴리즈 빌드는 커밋된 Mac 기본 설정과 Windows 기본 설정에서 만든다.

목소리 또는 모델을 직접 교체하는 절차는 [별도 안내](VOICE_MODELS.md)를 따른다.

## 릴리즈 제작

1. `chrome-extension/manifest.json`의 버전, `CHANGELOG.md`, 설치 지침을 갱신한다.
2. 모델 없는 검사를 실행하고 변경을 커밋한다. Git 작업 트리가 깨끗해야 배포 ZIP을 만들 수 있다.
3. 저장소 루트에서 실행한다.

   ```sh
   python3 tools/package_handoff.py
   python3 tools/verify_package.py artifacts/Dots-Voice-Mac.zip artifacts/Dots-Voice-Windows11.zip
   ```

4. `artifacts/`에 두 ZIP과 바깥 ZIP용 `SHA256SUMS.txt`가 생성된다. 각 ZIP의 `PACKAGE_INFO.json`에는 소스 커밋·버전·플랫폼·모델 revision이, 내부 `SHA256SUMS.txt`에는 전체 파일 해시가 기록된다. 명시한 파일만 포함하므로 모델·환경·로그·계정 정보가 섞이지 않는다. Windows `.cmd`는 CRLF, Mac `.command`는 실행 권한을 유지한다.
5. 해당 커밋을 GitHub에 푸시하고 같은 커밋에 버전 태그를 붙인다. GitHub Release의 Assets에 **두 ZIP과 바깥 `SHA256SUMS.txt`**를 올린다. 릴리즈 설명에 설치 링크와 실기기 검증 범위를 함께 기록한다.

예시(GitHub CLI가 인증된 유지관리자 환경):

```sh
git push origin HEAD:main
git tag v1.2.1
git push origin v1.2.1
gh release create v1.2.1 artifacts/Dots-Voice-Mac.zip artifacts/Dots-Voice-Windows11.zip artifacts/SHA256SUMS.txt --verify-tag --title 'Dots Voice v1.2.1' --notes-file docs/releases/v1.2.1.md
```

`--platform mac|windows`로 한쪽만 만들 수 있다. `--output-dir`로 출력 폴더를 바꿀 수 있다. `--allow-dirty`는 로컬 패키지 검사 전용이며, 이 옵션으로 만든 ZIP은 공개 릴리즈에 사용하지 않는다. 공개할 때는 GitHub에서 ZIP을 다시 내려받아 바깥 SHA-256과 내부 검증을 확인한다.

## 수동 연결과 실험

`tools/connect_offer.py --tts <offer.json>`은 확장 없이 신호를 교환하던 진단 경로다. `.tts-venv`의 Python으로 `src/tts_bridge_server.py`를 실행하고 `runtime/install-tts.js`를 dots 페이지에 넣은 뒤 생성한 offer를 사용한다. 일반 사용에는 확장을 권장한다.

`tools/tts_compare.py`, `tools/voice_candidates.py`는 Mac 비교 실험 도구다. 추가 모델을 내려받거나 메모리에 올릴 수 있으므로 통화 서버와 동시에 실행하지 않는다. 배포 참조 WAV를 자동으로 바꾸지 않는다. 초기 RVC 방식은 [보관 문서](../experiments/rvc/README.md)를 참고한다.
