# JWT/JWS 서비스 이해 메모

## 전체 프로젝트 한눈에 보기
- Attager IAM + 다중 에이전트 물류 시스템은 프론트엔드(포트 8006), 정책 서버(포트 8005), 네 개의 업무 에이전트(10001~10004)와 오케스트레이터, 두 종류의 Redis, 선택적 에이전트 레지스트리 등으로 구성된다.
- 저장소 루트에는 각 서비스별 디렉토리(`frontend/`, `iam/`, `Orchestrator_plugin/`, `agents/`, `agent-reg/`, `agentDB/`)가 정리되어 있고 `docker-compose.yml`로 전체 스택을 올릴 수 있다.

## jwt-server
- `fastapi` 기반 인증 서버로 `/token`에서 OAuth2 비밀번호 플로우를 받아 JWT를 발급하고, `/users/me`에서 토큰을 검증한다.
- `app/auth.py`는 `SECRET_KEY`, `ALGORITHM`, 만료 시간을 환경 변수(.env)로부터 읽어 JWT를 생성·검증하며, bcrypt 기반 비밀번호 해시/검증을 담당한다.
- `app/users.py`에는 임시 유저 DB가 있고, 발급된 토큰의 `sub`(이메일)와 `tenant` 클레임이 DB와 정확히 일치하는지 검사한 뒤 사용자 정보를 돌려준다.

## jws-server
- 별도의 FastAPI 앱으로, 서명된 에이전트 카드 토큰을 생성/검증하는 엔드포인트를 제공한다.
- `/sign`에서는 입력된 카드(`card`)나 카드 해시(`card_hash`)를 JCS 스타일로 정준화·SHA-256 해시 후 JWS에 `card_hash`, `version_id`, `etag`, `policy_version` 등을 포함해 HS256 알고리즘으로 서명한다.
- `/verify`는 전달된 JWS를 복호화하고, 선택적으로 클라이언트가 보낸 카드/해시와 토큰 내 `card_hash`가 일치하는지도 검사하여 위조 여부를 판별한다.
