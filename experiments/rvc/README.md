# 초기 RVC 실험 보관본

현재 Dots Voice의 기본 설치·실행 경로가 아니다. 통화 답변 자막을 TTS로 읽는 방식으로 전환하기 전에, 수신 음성을 RVC로 변환하던 실험을 보존한다. Mac·Windows 설치 ZIP에는 포함하지 않는다.

실험을 재현하려면 이 폴더에서 `sh setup.sh`를 실행하고 `.venv/bin/python bridge_server.py --model /path/to/model.pth`로 서버를 시작한다. Python 3.11, 별도로 사용 권한을 확보한 RVC 모델, 추가 의존성과 ContentVec 다운로드가 필요하다. 가상환경·모델·runtime·결과는 이 실험 폴더 아래에 만든다.

`dots-rtc.js`는 WebRTC 경로, `dots-rvc.js`와 `receive-poc.js`는 초기 관찰·연결 실험이다. 일반 사용자는 저장소 루트의 README를 따른다. 실험 스크립트는 현재 서비스 UI와 재검증되지 않았다.
