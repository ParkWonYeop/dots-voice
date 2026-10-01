# 라이선스 적용 범위와 외부 구성 요소

## Dots Voice

이 프로젝트의 자체 코드, 문서, 설정 및 리소스는 루트의 [MIT License](LICENSE)를 따릅니다. 저작권자는 `Copyright (c) 2026 ParkWonYeop`입니다. 재배포할 때 저작권 고지와 라이선스 전문을 함께 유지하세요.

## 포함된 합성 참조 음성

`voices/designed-soft.wav`는 Qwen3-TTS VoiceDesign으로 생성한 합성 캐릭터 음성입니다. 배포자가 이 파일에 대해 보유한 권리가 있는 범위에서 동일한 MIT License로 제공합니다. 이는 생성 모델 자체의 라이선스를 변경하지 않습니다.

- 생성 모델: [mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit), revision `5c390979e4b93af5f2932f90742ca99c7dd04687`.
- 생성 설정과 프롬프트: [config/voice_candidates.json](config/voice_candidates.json)의 `designed_soft` 항목.
- 샘플 정보와 SHA-256: [voices/designed-soft.json](voices/designed-soft.json).

## 별도로 내려받는 모델·라이브러리

모델 가중치와 설치되는 라이브러리는 Git 저장소와 설치 ZIP에 포함하지 않습니다. 이 구성 요소에는 각각의 원래 라이선스가 적용되며, Dots Voice의 MIT License로 재허가하지 않습니다.

| 구성 요소 | 라이선스·출처 |
| --- | --- |
| Qwen3-TTS 코드 | [Apache-2.0](https://github.com/QwenLM/Qwen3-TTS/blob/main/LICENSE) |
| Mac 기본 모델 | [Qwen3-TTS-12Hz-0.6B-Base-4bit · Apache-2.0](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit) |
| Windows 기본 모델 | [Qwen3-TTS-12Hz-0.6B-Base · Apache-2.0](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) |
| 참조 음성 생성 모델 | [Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit · Apache-2.0](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-4bit) |
| MLX Audio | [MIT](https://github.com/Blaizzy/mlx-audio/blob/main/LICENSE) |

위 표는 주요 구성 요소의 출처 안내입니다. 그 밖의 직접·간접 의존성은 `requirements/`의 해당 플랫폼 목록과 설치된 패키지의 라이선스 고지를 확인하세요. 모델·라이브러리를 별도로 묶어 재배포한다면 해당 구성 요소의 라이선스와 필요한 고지도 함께 제공해야 합니다.

이전 RVC 실험에서 별도로 받는 코드·가중치에도 각 원본의 조건이 적용됩니다. 해당 실험과 다운로드 파일은 설치 ZIP에 포함하지 않습니다.
