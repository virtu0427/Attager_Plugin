# Orchestrator Chat Client (독립 UI)

오케스트레이터 에이전트와 대화하기 위한 최소 웹 UI입니다. 기존 `frontend/` Flask 앱과 별도의 FastAPI 서버로 구동되며, JSON-RPC `message/send`를 통해 오케스트레이터와 통신합니다. JWT 인증 서버에서 로그인한 세션만 `/chat` 경로에 접근할 수 있고, 나머지 사용자는 `/login` 화면으로 리디렉션됩니다.

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

- 클라이언트 UI: http://localhost:8010 (초기 접속 시 `/login`으로 리디렉션)
- 오케스트레이터 JSON-RPC: http://localhost:10000/
- JWT Auth 서버: http://localhost:8011/


## 환경 변수
- `ORCHESTRATOR_RPC_URL` (선택): 오케스트레이터 JSON-RPC 엔드포인트. 기본값은 `http://localhost:10000/` 입니다.
- `JWT_SERVER_URL` (선택): JWT 인증 서버 엔드포인트. 기본값은 `http://localhost:8011` 입니다.
- `SESSION_COOKIE_NAME` (선택): 로그인 세션 쿠키 이름. 기본값은 `chat_session` 입니다.
- `SESSION_COOKIE_MAX_AGE` (선택): 세션 쿠키 만료 시간(초). 기본값은 `3600` 입니다.
- `SESSION_COOKIE_SECURE` (선택): `true`로 설정하면 HTTPS에서만 쿠키를 전송합니다.

## 로그인 흐름
로그인에 성공하기 전까지는 `/login` 페이지만 표시됩니다.
1. `/login` 페이지의 폼에서 이메일/비밀번호를 입력해 `/api/login`으로 요청합니다.
2. 서버가 `JWT_SERVER_URL`의 `/token` 엔드포인트에 OAuth2 Password Grant로 위임해 토큰을 발급받습니다.
3. 발급받은 토큰으로 `/users/me`를 호출해 사용자 정보를 검증합니다.
4. 검증이 끝나면 FastAPI 서버가 HTTP-only 세션 쿠키를 발급하고 `/chat`으로 이동합니다.
5. `/chat`에서 새로고침을 하거나 직접 접근하더라도 유효한 세션이 없으면 `/login`으로 리디렉션됩니다.
6. 우측 사용자 카드에 있는 **로그아웃** 버튼을 누르면 세션이 제거되고 `/login`으로 돌아갑니다.

> 예시 계정 (기본 더미 데이터)
> - `user@example.com / password123`
> - `user2@example.com / password1234`
> - `admin@example.com / admin123`

## 동작 흐름
- `/api/login` → JWT 서버와 통신해 토큰을 발급받고 사용자 정보를 검증한 뒤 서버 세션에 저장
- `/api/session` → 현재 세션의 사용자 정보를 조회 (채팅 화면에서 자동 호출)
- `/api/logout` → 서버 세션 삭제 및 쿠키 제거
- `/api/chat` → `message/send` JSON-RPC 요청을 작성해 오케스트레이터로 전달 (서버 세션 또는 명시적 Authorization 헤더가 없으면 거부)
- 응답 결과의 `parts.text`를 우선 추출해 채팅 화면에 표시
- UI와 서버는 `client/` 디렉터리 안에서만 동작하며, 기존 Flask UI와 포트/서버가 분리됩니다.
