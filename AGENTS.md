# Dots Voice 개발 지침

- 이 저장소의 개발 작업은 README.md와 docs/DEVELOPMENT.md를 기준으로 한다. 하위 에이전트를 사용하지 않는다.
- 설치 요청은 운영체제별 packaging/macos 또는 packaging/windows의 AGENTS.md와 SETUP.md를 따른다. 배포 ZIP에는 이 지침들이 루트에 복사된다.
- 선택한 voices/designed-soft.wav, 모델 ID·revision, 확장 공개 키를 사용자 요청 없이 바꾸지 않는다.
- src/는 실행 코드, chrome-extension/은 브라우저 코드, config/는 설정, tests/는 검사, tools/는 개발·배포 도구다.
- 폴더 구조를 바꾸면 설치기, 네이티브 실행기, 패키지 허용 목록, 검사, 설치 문서의 경로를 함께 갱신한다.
- 변경에 맞는 검사를 tools/check.py로 실행한다. 릴리즈 ZIP은 tools/verify_package.py로 검증한다. Windows 모의 검사 통과를 실기기 통화 확인으로 보고하지 않는다.
- 모델·가상환경·runtime·로그·개인 경로·계정 정보는 커밋하거나 배포하지 않는다. runtime/tts-bridge-config.json의 토큰을 출력하지 않는다.
- Chrome 확장 등록·새로고침은 사용자가 직접 한다. 보안 설정이나 Chrome 프로필을 우회 수정하지 않는다.
- 작업 단위로 커밋하고 구성된 원격 저장소에 푸시한다. 릴리즈는 깨끗한 커밋에서 빌드하고 해당 커밋을 가리키는 태그로 올린다.
