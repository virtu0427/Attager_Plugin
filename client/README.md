# Orchestrator Chat Client (독립 UI)

오케스트레이터 에이전트와 대화하기 위한 최소 웹 UI입니다. 기존 `frontend/` Flask 앱과 별도의 FastAPI 서버로 구동되며, JSON-RPC `message/send`를 통해 오케스트레이터와 통신합니다. 이제 JWT 인증 서버로부터 토큰을 발급받아야만 채팅을 시작할 수 있으며, `/login`에서 로그인 후 `/chat` 페이지로 이동해 채팅을 진행합니다.

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

- 클라이언트 UI: http://localhost:8010/login (성공 시 `/chat`)
- 오케스트레이터 JSON-RPC: http://localhost:10000/
- JWT Auth 서버: http://localhost:8011/


## 환경 변수
- `ORCHESTRATOR_RPC_URL` (선택): 오케스트레이터 JSON-RPC 엔드포인트. 기본값은 `http://localhost:10000/` 입니다.
- `JWT_SERVER_URL` (선택): JWT 인증 서버 엔드포인트. 기본값은 `http://localhost:8011` 입니다.

## 로그인 흐름
`/login` 페이지에서 인증에 성공하기 전까지는 `/chat`으로 이동할 수 없습니다.
1. `/login` 페이지의 폼에서 이메일/비밀번호를 입력해 `/api/login`으로 요청합니다.
2. 서버가 `JWT_SERVER_URL`의 `/token` 엔드포인트에 OAuth2 Password Grant로 위임해 토큰을 발급받습니다.
3. 발급받은 토큰으로 `/users/me`를 호출해 사용자 정보를 검증합니다.
4. 로그인에 성공하면 `/chat` 페이지로 리다이렉트되며, 채팅 입력란이 활성화되고 사용자 정보 카드에 이메일/테넌트가 표시됩니다.

> 예시 계정 (기본 더미 데이터)
> - `user@example.com / password123`
> - `user2@example.com / password1234`
> - `admin@example.com / admin123`

## 동작 흐름
- `/api/login` → JWT 서버와 통신해 토큰을 발급받고 사용자 정보를 검증
- `/api/chat` → `message/send` JSON-RPC 요청을 작성해 오케스트레이터로 전달 (Authorization 헤더 필요)
- 응답 결과의 `parts.text`를 우선 추출해 채팅 화면에 표시
- UI와 서버는 `client/` 디렉터리 안에서만 동작하며, 기존 Flask UI와 포트/서버가 분리됩니다.
