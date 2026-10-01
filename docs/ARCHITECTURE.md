# 연결 구조

1. 사용자가 dots 대화 탭에서 확장 버튼을 누른다.
2. 확장 background가 Chrome Native Messaging으로 `src/voice_launcher.py`를 호출한다.
3. 실행기는 현재 폴더·설정과 일치하는 서버를 재사용하거나 전용 Python 환경으로 TTS 서버를 시작한다.
4. 확장은 해당 탭에 자막·오디오 후크를 넣고 SDP offer/answer를 네이티브 실행기를 통해 교환한다.
5. 브라우저와 로컬 서버의 WebRTC 연결이 준비되면 원래 수신 음성을 음소거한다. assistant 자막을 구절로 묶어 TTS에 보내고 합성 PCM을 재생한다.
6. 사용자 발화 자막이 도착하면 현재 합성과 대기 음성을 취소한다. 연결 실패나 복원 동작에서는 원래 음성으로 돌아간다.

## 구성요소

| 위치 | 역할 |
| --- | --- |
| `chrome-extension/background.js` | 중복 연결 방지, 단계 알림, 문서별 주입, 네이티브 메시지 |
| `chrome-extension/popup.*` | 연결·미리듣기·복원과 상태 표시 |
| `chrome-extension/dots-tts.js` | 수신 오디오·자막 관찰, WebRTC 연결, 원음 제어 |
| `chrome-extension/transcript_buffer.js` | 증분 자막 중복 제거, 구절 묶기, 답변 취소 |
| `src/voice_launcher.py` | 네이티브 프로토콜, 서버 잠금·시작·검증·종료 |
| `src/tts_bridge_server.py` | 인증된 loopback 서버, 음성 큐, MLX 엔진, WebRTC PCM 출력 |
| `src/tts_worker.py` | 추론 자식 프로세스와 취소·재사용 |
| `src/tts_torch_engine.py` | Windows용 Qwen3-TTS 구절 합성 |
| `src/audio_stream.py` | 청크 간 상태를 유지하는 리샘플링과 무음 보정 |
| `src/setup_*.py` | 플랫폼별 의존성·모델·확장·네이티브 호스트 설치 |

## 두 합성 경로

Mac은 MLX의 PCM 청크를 생성되는 대로 전달한다. Windows의 공식 Qwen3-TTS API는 구절 전체를 합성한 뒤 반환한다. Windows에서 전송용 PCM을 나누더라도 추론 자체가 실시간 스트리밍으로 바뀌지는 않는다.

두 플랫폼 모두 같은 참조 WAV의 화자 특성을 사용하지만 모델 정밀도와 라이브러리가 달라 음색·운율·속도가 달라질 수 있다. 참조 텍스트를 추가해 ICL 경로로 바꾸거나 참조 WAV를 재생성하지 않는다.

## 로컬 상태

모델과 가상환경은 설치 폴더 안에 있다. 서버는 `127.0.0.1:8766`에만 바인딩하며 신호 교환·종료 요청에는 임시 인증 토큰을 요구한다. 토큰은 네이티브 실행기에 남고 페이지와 확장에는 전달하지 않는다. 네이티브 호스트는 고정 확장 ID 하나를 허용한다.

Mac 호스트는 사용자 Application Support, Windows 호스트는 현재 사용자 레지스트리에 등록된다. 확장은 클릭한 dots 탭에만 코드를 주입한다. Chrome 페이지 구현에 의존하는 관찰 후크이므로 서비스 변경 시 재검증이 필요하다.
