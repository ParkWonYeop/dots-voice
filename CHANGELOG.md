# 변경 기록

## 1.2.2 · 2026-10-01

- 자체 코드·문서·설정·리소스에 MIT License 적용.
- 외부 모델·라이브러리와 합성 참조 음성의 라이선스 적용 범위·출처 안내 추가.
- Mac·Windows 설치 ZIP에 `LICENSE`와 `THIRD_PARTY_NOTICES.md` 포함 및 패키지 검사에 반영.

## 1.2.1 · 2026-10-01

- 확장 UI·설치 안내·코드에서 목소리 명칭을 로컬 목소리로 통일.
- Mac 설치 파일을 `install-mac.command`로 변경.
- 참조 WAV·Base 모델 교체, 플랫폼별 설정, 적용·검증·원복 문서 추가 및 두 ZIP에 동봉.
- 기본 참조 WAV, 모델 revision과 확장 공개 키는 유지.

## 1.2.0 · 2026-10-01

첫 GitHub 공개 릴리즈입니다.

- Mac Apple Silicon / Windows 11 x64 전용 설치 ZIP과 SHA-256 제공.
- 각 ZIP에 수동 설치 안내, `AGENTS.md`, `CLAUDE.md`, 상세 진단 절차, `AGENT_PROMPT.txt` 포함.
- Chrome 확장 버튼으로 서버 시작·재사용·연결, 진행 단계·상태 표시, 미리듣기·원래 목소리 복원.
- 고정 참조 목소리, 자막 묶음 처리, 발화 중단 시 합성 취소, 연속 리샘플링·무음 보정.
- Mac MLX 스트리밍, Windows PyTorch 사양 검사·CUDA/CPU 선택·설치 시 합성 측정.
- 소스·설정·검사·배포 도구·이전 실험을 분리하고 ZIP 무결성·실행기 검증 추가.

Mac에서 코드·오디오 처리·네이티브 호스트 검사를 수행했습니다. Windows 실기기 합성·Chrome 통화는 미검증이며, Mac과 동일한 음색·속도를 보장하지 않습니다.
