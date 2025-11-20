# 프로젝트 인수인계 문서

## 1. 프로젝트 한눈에 보기
- **이름**: Attager IAM + 다중 에이전트 물류 시스템
- **목표**: Google Gemini 및 로컬 LLM을 활용한 도메인별 에이전트 운영과 IAM 정책·로그 관리 UI 제공
- **주요 구성 요소**:
  - Flask 기반 **관리 프론트엔드** (`frontend/`, 포트 8006)
  - FastAPI 기반 **IAM 정책 서버** (`Orchestrator_plugin/server_redis.py`, 포트 8005)
  - FastAPI 기반 **오케스트레이터 클라이언트/게이트웨이** (`client/app.py`, 포트 8010) – `/login`→`/chat` 경로 분리, 서버 세션/쿠키로 JWT 유지
  - 4종 도메인 **업무 에이전트** (배송, 상품, 품질, 차량)과 오케스트레이터 (`agents/`, `Orchestrator_new/`)
  - **JWT 발급 서버** (`jwt-server/`, 포트 8011)와 **JWS 서명 서버** (`jws-server/`, 포트 8012)
  - **Redis 2종 분리**: 업무 데이터(`redis-agents`, 포트 6379)와 IAM/정책 데이터(`redis-iam`, 포트 6380)
  - **Agent Registry**(옵션)와 프론트 UI (`agent-reg/`, `agent-reg/frontend/`)

## 2. 저장소 구조 요약
```
├── frontend/                # Flask 앱, 템플릿, 정적 리소스, IAM Redis 연동
├── iam/                     # A2A 다중 에이전트 보안 솔루션 (정책 플러그인/DB 래퍼)
├── Orchestrator_plugin/     # FastAPI 정책 서버, 정책/로그 API, Dockerfile
├── Orchestrator_new/        # 로컬 오케스트레이터 실행 엔트리 (개발용)
├── agents/                  # 업무용 에이전트 (delivery/item/quality/vehicle)
│   └── */tools/redis_*      # 각 에이전트 Redis 툴, AGENT_REDIS_* 환경변수 지원
├── agentDB/                 # 에이전트 Redis 시드 스크립트 및 Docker 이미지
├── agent-reg/               # 에이전트 레지스트리 백엔드 (옵션 서비스)
├── docker-compose.yml       # 전체 스택 오케스트레이션, Redis 2종 및 의존성 정의
├── ARCHITECTURE.md          # 시스템 아키텍처 상세 설명
├── DOCKER_GUIDE.md          # Docker 실행 가이드
├── GEMINI_SETUP.md          # Gemini API 설정 안내
└── README.md                # 전반적 개요 및 수동 실행 지침
```

## 3. 서비스 및 포트 매핑
| 컴포넌트 | 경로 | 기술 스택 | 기본 포트 | 주요 환경 변수 |
| --- | --- | --- | --- | --- |
| 프론트엔드 IAM UI | `frontend/` | Flask + Vanilla JS | 8006 | `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `PORT` |
| IAM 정책 서버 | `Orchestrator_plugin/` | FastAPI | 8005 | `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `PORT` |
| 오케스트레이터 게이트웨이/클라이언트 | `client/` | FastAPI | 8010 | `JWT_SERVER_URL`, `SESSION_SECRET`, `ORCHESTRATOR_RPC_URL` |
| JWT 인증 서버 | `jwt-server/` | FastAPI | 8011 | `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXP_MINUTES` |
| JWS 서명 서버 | `jws-server/` | FastAPI | 8012 | `PRIVATE_KEY_PATH`, `PUBLIC_KEY_PATH` |
| 오케스트레이터 | `Orchestrator_new/` | Python CLI | 10000 | `POLICY_SERVER_URL`, `LOG_SERVER_URL` |
| 업무 에이전트 (배송/상품/품질/차량) | `agents/*` | FastAPI + Gemini SDK | 10001~10004 | `AGENT_REDIS_HOST/PORT/DB`, `POLICY_SERVER_URL`, `LOG_SERVER_URL`, `GOOGLE_API_KEY` |
| 에이전트 Redis | `redis-agents` | Redis 7 | 6379 | `AGENT_REDIS_*` |
| IAM Redis | `redis-iam` | Redis 7 | 6380(외부) / 6379(컨테이너) | `REDIS_*` |
| 에이전트 레지스트리 | `agent-reg/` | FastAPI | 8000 | `DATABASE_PATH` |
| 레지스트리 프론트 | `agent-reg/frontend/` | React | 3000 | `REACT_APP_*` |

## 4. Docker Compose 기반 구동 절차
1. 루트에 `.env` 작성 (필수 항목)
   ```bash
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
   USE_GEMINI=true
   FALLBACK_TO_LOCAL=true
   OLLAMA_HOST=host.docker.internal
   SESSION_SECRET=changeme-session
   JWT_SECRET_KEY=supersecretjwt
   JWT_ALGORITHM=HS256
   JWT_EXP_MINUTES=60
   ```
2. 빌드 및 실행
   ```bash
   docker compose up --build
   ```
   - `redis-agents` → `agent-redis-seeder` → 업무 에이전트 순으로 기동됩니다.
   - `redis-iam`은 프론트엔드와 정책 서버가 공유합니다.
3. 주요 접속 포인트
   - 오케스트레이터 게이트웨이(로그인 진입): http://localhost:8010/login → 로그인 성공 시 `/chat`
   - 정책 서버 헬스체크: http://localhost:8005/health
   - JWT 서버: http://localhost:8011 (발급 및 검증 테스트용)
   - JWS 서버: http://localhost:8012 (카드 서명/검증 테스트용)
   - IAM UI: http://localhost:8006
   - 각 에이전트 API: http://localhost:1000X/docs

### 수동 종료 및 정리
```bash
docker compose down -v   # 데이터 볼륨까지 초기화
```

## 5. Redis 데이터 및 시드 전략
- **에이전트 Redis (`redis-agents`)**
  - 시드 데이터: `agentDB/seed_data.txt`
  - 시드 스크립트: `agentDB/seed_agent_data.py`
  - Docker 실행 시 `agent-redis-seeder` 컨테이너가 자동 실행 (healthcheck 대기 + 멱등 시드)
  - 수동 시드 예시: `AGENT_REDIS_HOST=localhost python agentDB/seed_agent_data.py`
- **IAM Redis (`redis-iam`)**
  - 기본 데이터는 `iam/database.py` 초기화 로직(프론트엔드 호환용 래퍼: `frontend/database.py`)으로 적재 (에이전트/룰셋/정책/로그 키)
  - 프론트엔드에서 CRUD 수행 시 즉시 Redis에 반영

## 6. 주요 코드/모듈 설명
- `client/app.py`
  - FastAPI 기반 오케스트레이터 게이트웨이로 `/login`, `/chat`, `/api/session`, `/api/logout`, `/api/chat` 라우팅을 제공
  - 로그인 시 JWT 서버에서 토큰을 받아 서버 측 세션/쿠키에 저장하고, 채팅 요청 시 사용자 이메일·JWT 스킴/토큰을 헤더로 오케스트레이터에 전달
  - 세션이 없으면 `/chat`과 `/api/chat` 요청은 FastAPI 레벨에서 401로 차단
- `client/public/login.html`, `client/public/chat.html`, `client/static/app.js`, `client/static/style.css`
  - 로그인/채팅 UI를 분리한 정적 리소스, 로그인 후에만 채팅 화면을 렌더링하며 헤더에 사용자 정보를 표시
- `frontend/app.py`
  - Flask Blueprints 없이 단일 앱으로 `/dashboard`, `/agents`, `/ruleset`, `/logs` 페이지 제공
  - `/api/graph/agent-flow`, `/api/stats/overview` 등 데이터 엔드포인트 포함
  - Redis 커넥션은 `frontend/database.get_db()`를 통해 주입
- `frontend/database.py`
  - 프론트엔드 호환을 위한 래퍼 모듈로, 실제 CRUD 로직은 `iam/database.py`에 위임
- `iam/database.py`
  - IAM Redis 헬퍼 (에이전트, 룰셋, 정책, 로그 CRUD + 통계)
  - 새 인스턴스 생성 시 기본 데이터 자동 세팅 → Docker/로컬 환경에서 초기 화면 보장
- `iam/policy_enforcement.py`
  - A2A 환경 공용 IAM 정책 플러그인 (프롬프트/툴 검증 + 감사 로그 전송)
  - 오케스트레이터에서 전달한 사용자 JWT/이메일을 컨텍스트에서 추출해 인증이 필요한 툴 호출을 필터링
- `frontend/*/*.js`
  - 순수 JS로 API 호출·렌더링 처리 (한글 UI 기준)
  - MiniSearch 기반 로그 검색 (`frontend/logs/logs.js`)
- `Orchestrator_plugin/server_redis.py`
  - FastAPI 앱, Redis 기반 정책 조회·로그 수집 엔드포인트 제공
  - 에이전트와 프론트엔드가 공유하는 JSON 구조 유지
- `agents/*/tools/redis_*`
  - 업무 Redis 연결 모듈, `AGENT_REDIS_HOST/PORT/DB` 우선 → Docker/클라우드 환경 분리 가능
- `agentDB/Dockerfile.seeder`
  - 최소한의 Python 이미지 + `seed_agent_data.py` 실행용 컨테이너 정의

## 7. 로컬 개발 시나리오
### 오케스트레이터 클라이언트(로그인/채팅) 테스트
```bash
pip install -r requirements.txt
export JWT_SERVER_URL=http://localhost:8011
export ORCHESTRATOR_RPC_URL=http://localhost:10000/
export SESSION_SECRET=devsecret
python client/app.py  # 8010
```
- 브라우저에서 `http://localhost:8010/login` 진입 → 로그인 성공 시 `/chat` 전환, 세션 쿠키로 JWT 저장
- `/api/chat` 호출 시 Authorization 헤더에 세션의 JWT 스킴/토큰을 붙여 오케스트레이터/에이전트가 사용자별 정책을 적용

### 프론트엔드만 수정하고 싶을 때
```bash
pip install -r requirements.txt
export REDIS_HOST=localhost REDIS_PORT=6380 REDIS_DB=0
python frontend/app.py  # 8006
```
- 별도의 Redis 실행 필요 (`docker run -p 6380:6379 redis:7-alpine` 등)

### 단일 에이전트 테스트
```bash
pip install -r requirements.txt
export AGENT_REDIS_HOST=localhost AGENT_REDIS_PORT=6379
export POLICY_SERVER_URL=http://localhost:8005
python agents/delivery_agent/__main__.py
```
- 업무 Redis가 비어 있으면 `agentDB/seed_agent_data.py`로 선 시드 필요

### 정책 서버 단독 실행
```bash
pip install -r requirements.txt
export REDIS_HOST=localhost REDIS_PORT=6380
python Orchestrator_plugin/server_redis.py
```

## 8. 배포 및 확장 고려 사항
- **환경 변수 기반 구성**: 모든 Redis/포트/외부 엔드포인트는 환경 변수로 오버라이드 가능 → 클라우드 환경에서 서비스 디스커버리 적용 용이
- **로그·정책 데이터 분리**: IAM Redis는 정책/로그만 저장, 업무 Redis는 도메인 데이터 저장 → 보안·스케일링 분리 가능
- **시드 멱등성**: `agent-redis-seeder`는 `agent_seed:version` 키를 활용해 중복 로드를 방지, `AGENT_REDIS_FORCE_RESEED=true`로 재시드 가능
- **오케스트레이터 로컬 경로 주의**: `Orchestrator_plugin/agent.py`는 로컬에서 실행, Docker 내부 에이전트와 통신할 때 `POLICY_SERVER_URL`을 반드시 컨테이너 내부 주소로 설정
- **추가 에이전트 확장**: `docker-compose.yml` 패턴을 따라 새로운 에이전트 서비스 추가, Redis/포트/의존성 명시 후 IAM 정책에 등록

## 9. 운영 중 확인해야 할 항목
- **Redis 연결 실패**: 에이전트 컨테이너 로그에서 `ConnectionError` 확인 → `AGENT_REDIS_HOST` 설정 또는 네트워크 체크
- **정책 미적용**: 정책 서버의 `/api/iam/policy/{agent_id}` 응답 구조 확인, 정책 미존재 시 프론트에서 정책 생성 필요
- **로그 미수집**: 에이전트에서 `LOG_SERVER_URL` 설정 확인, 정책 서버 `/api/logs` 호출 로그 조사
- **UI 데이터 이상**: 프론트엔드 API `/api/stats/overview`, `/api/logs/search` 응답 JSON 검증
- **채팅 인증 문제**: `/api/session` 응답에서 `token_type`/`access_token` 확인, 세션 쿠키가 없으면 `/login`에서 재인증 후 `/chat` 접근
- **JWT 전달 확인**: 오케스트레이터/에이전트 호출 헤더에 `Authorization`과 `X-User-Email`이 포함되는지 로그로 점검

## 10. 커뮤니케이션 및 향후 작업 메모
- 프론트엔드 레이아웃은 국문화된 상태이며, 추가 컴포넌트 개발 시 동일한 그리드/폰트 규칙 유지 필요 (`frontend/style.css` 참고)
- Gemini API 키는 실제 운영 시 Secret Manager나 Vault 연동 고려
- 로그 고도화(예: ElasticSearch 연동) 및 IAM 정책 스키마 버전 관리가 후속 과제로 남아 있음
- Kubernetes 이전을 고려할 경우, Redis 2종을 각기 StatefulSet으로 구성하고 시드 잡(CronJob) 분리 권장
- IAM 공통 모듈(`iam/`)은 모든 컨테이너에서 동일 경로(`/app/iam`)로 복사하거나 마운트해야 하며, 신규 Dockerfile 작성 시 `COPY iam /app/iam` 및 루트 `requirements.txt` 설치를 필수로 포함하세요.

## 11. A2A 보안 솔루션 적용 주의사항
- **보안 솔루션 모듈 분리**: A2A 환경에서 공통으로 사용하는 IAM 보안 컴포넌트는 `iam/` 패키지에 집약되어 있습니다. 새로운 에이전트나 오케스트레이터에서 정책 플러그인을 사용할 때는 반드시 `from iam.policy_enforcement import PolicyEnforcementPlugin` 형태로 임포트해 주세요.
- **사용자 컨텍스트 전달**: 오케스트레이터 클라이언트가 `/api/chat` 호출 시 `Authorization`(JWT 스킴/토큰)과 `X-User-Email`을 헤더에 붙이고, 정책 플러그인은 이를 컨텍스트에서 읽어 인증이 필요한 툴을 필터링합니다. 에이전트 측 로직을 수정하지 않아도 플러그인을 통해 사용자별 툴 제한을 적용할 수 있습니다.
- **환경별 의존성 분리**: 실행 환경 스크립트(`agents/*`, `Orchestrator_new/`)는 에이전트 로직에 집중하고, 보안 로직은 `iam/`을 통해 주입합니다. 환경 설정 변경 시 보안 로직을 직접 수정하지 말고 환경 변수(`POLICY_SERVER_URL`, `LOG_SERVER_URL`, `GOOGLE_API_KEY`)만 조정해야 합니다.
- **IAM 룰 검증 절차**: 정책 서버(`Orchestrator_plugin/server_redis.py`)는 Redis에 저장된 룰셋을 그대로 반환합니다. 새로운 룰을 추가하거나 정책을 변경한 뒤에는 `iam.policy_enforcement.PolicyEnforcementPlugin.fetch_policy()`를 호출하거나 서비스 재기동으로 정책을 갱신하고, `/api/iam/policy/{agent_id}` 응답 구조(`prompt_validation_rules`, `tool_validation_rules`)가 플러그인에서 기대하는 스키마와 일치하는지 확인하세요.
- **로그 수집 확인**: 플러그인은 정책 위반 시 `/api/logs` 엔드포인트로 감사 로그를 전송합니다. 로그 저장소가 분리된 환경에서는 해당 엔드포인트를 프록시하거나 IAM Redis에 쓰기 권한을 가진 API 게이트웨이를 구성해야 합니다.
- **Docker 개발 모드 주의**: `frontend` 서비스는 소스 볼륨(`./frontend:/app`)을 마운트하므로, 분리된 `iam/` 패키지가 `/app/iam`에 추가로 마운트되도록 `docker-compose.yml`에 `./iam:/app/iam:ro`가 선언되어 있습니다. 커스텀 Compose 파일을 작성할 때도 동일한 마운트를 포함해야 `import iam` 오류가 발생하지 않습니다.
- **공유 패키지 의존성**: 모든 에이전트와 정책 서버 Dockerfile이 루트 `requirements.txt`를 설치하고 `iam/` 디렉터리를 이미지에 복사하도록 갱신되었습니다. 신규 이미지를 작성할 때도 동일한 패턴을 따라야 `PolicyEnforcementPlugin`과 Redis 래퍼가 동작합니다.

## 12. 다음 담당자를 위한 체크리스트
- [ ] `docker compose up --build` 실행 후 `attager-frontend`, `attager-policy-server`, `orchestrator-client` 로그에서 `ModuleNotFoundError`가 발생하지 않는지 확인 (IAM 패키지 마운트·세션 비밀키 설정)
- [ ] 정책 서버 `/api/iam/policy/{agent_id}` 응답에 `prompt_validation_rules`와 `tool_validation_rules`가 포함되는지 점검하고, 누락 시 `iam/database.py` 초기 데이터 또는 프론트엔드 정책 편집 UI로 수정
- [ ] 오케스트레이터 클라이언트 `/login`→`/chat` 흐름에서 세션 쿠키가 설정되고 `/api/session`에 `token_type`/`access_token`/`email`이 노출되는지 확인
- [ ] `/api/chat` 경로로 전달되는 요청 헤더에 `Authorization`과 `X-User-Email`이 포함되는지 샌드박스 에이전트 호출 로그로 검증
- [ ] 보안 정책 변경 후에는 `PolicyEnforcementPlugin.reload_policy_cache()` 호출 또는 정책 서버 재기동으로 최신 룰이 적용되었는지 테스트 시나리오(예: 샌드박스 에이전트 호출)로 확인

> 위 체크리스트는 후속 LLM/개발자가 동일한 보안 모듈 기반으로 작업할 때 발생할 수 있는 호환성 문제를 선제적으로 방지하기 위한 최소 점검 항목입니다.

---
이 문서는 새로운 에이전트나 개발자가 빠르게 환경을 이해하고 기동할 수 있도록 현재 구성과 절차를 요약합니다. 추가 질문이나 업데이트는 `ARCHITECTURE.md`, `DOCKER_GUIDE.md`, `README.md`를 참고하거나 최신 변경 사항 커밋 메시지를 확인하세요.
