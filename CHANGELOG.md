# 변경 기록

## 1.2.0 · 2026-10-01

첫 GitHub 공개 릴리즈입니다.

- Mac Apple Silicon / Windows 11 x64 전용 설치 ZIP과 SHA-256 제공.
- 각 ZIP에 수동 설치 안내, `AGENTS.md`, `CLAUDE.md`, 상세 진단 절차, `AGENT_PROMPT.txt` 포함.
- Chrome 확장 버튼으로 서버 시작·재사용·연결, 진행 단계·상태 표시, 미리듣기·원래 목소리 복원.
- 고정 참조 목소리, 자막 묶음 처리, 발화 중단 시 합성 취소, 연속 리샘플링·무음 보정.
- Mac MLX 스트리밍, Windows PyTorch 사양 검사·CUDA/CPU 선택·설치 시 합성 측정.
- 소스·설정·검사·배포 도구·이전 실험을 분리하고 ZIP 무결성·실행기 검증 추가.

Mac에서 코드·오디오 처리·네이티브 호스트 검사를 수행했습니다. Windows 실기기 합성·Chrome 통화는 미검증이며, Mac과 동일한 음색·속도를 보장하지 않습니다.
