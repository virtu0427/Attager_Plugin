# Orchestrator Chat Client (독립 UI)

오케스트레이터 에이전트와 대화하기 위한 최소 웹 UI입니다. 기존 `frontend/` Flask 앱과 별도의 FastAPI 서버로 구동되며, JSON-RPC `message/send`를 통해 오케스트레이터와 통신합니다.

## 실행 방법
1. 의존성 설치 (루트 `requirements.txt` 사용)
   ```bash
   pip install -r requirements.txt
   ```
2. 서버 실행 (기본 포트 `8010`)
   - 저장소 루트에서 실행할 때
     ```bash
     uvicorn client.app:app --reload --host 0.0.0.0 --port 8010
     ```
   - Windows 등에서 `ModuleNotFoundError: No module named 'client'` 가 날 경우
     `client` 디렉터리로 이동한 뒤 스크립트를 직접 실행하세요.
     ```bash
     cd client
     python app.py
     ```

### Docker Compose로 실행
루트 `docker-compose.yml`에 `orchestrator`와 `orchestrator-client` 서비스가 추가되었습니다.

```bash
# 오케스트레이터 서버와 클라이언트 UI 동시 실행
docker compose up --build orchestrator orchestrator-client
```

- 클라이언트 UI: http://localhost:8010
- 오케스트레이터 JSON-RPC: http://localhost:10000/


## 환경 변수
- `ORCHESTRATOR_RPC_URL` (선택): 오케스트레이터 JSON-RPC 엔드포인트. 기본값은 `http://localhost:10000/` 입니다.

## 동작 흐름
- `/api/chat` → `message/send` JSON-RPC 요청을 작성해 오케스트레이터로 전달
- 응답 결과의 `parts.text`를 우선 추출해 채팅 화면에 표시
- UI와 서버는 `client/` 디렉터리 안에서만 동작하며, 기존 Flask UI와 포트/서버가 분리됩니다.
