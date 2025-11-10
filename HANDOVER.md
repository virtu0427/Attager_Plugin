# 프로젝트 인수인계 문서

## 1. 프로젝트 한눈에 보기
- **이름**: Attager IAM + 다중 에이전트 물류 시스템
- **목표**: Google Gemini 및 로컬 LLM을 활용한 도메인별 에이전트 운영과 IAM 정책·로그 관리 UI 제공
- **주요 구성 요소**:
  - Flask 기반 **관리 프론트엔드** (`frontend/`, 포트 8006)
  - FastAPI 기반 **IAM 정책 서버** (`Orchestrator_plugin/server_redis.py`, 포트 8005)
  - 4종 도메인 **업무 에이전트** (배송, 상품, 품질, 차량)과 오케스트레이터 (`agents/`, `Orchestrator_new/`)
  - **Redis 2종 분리**: 업무 데이터(`redis-agents`, 포트 6379)와 IAM/정책 데이터(`redis-iam`, 포트 6380)
  - **Agent Registry**(옵션)와 프론트 UI (`agent-reg/`, `agent-reg/frontend/`)

## 2. 저장소 구조 요약
```
├── frontend/                # Flask 앱, 템플릿, 정적 리소스, IAM Redis 연동
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
   ```
2. 빌드 및 실행
   ```bash
   docker compose up --build
   ```
   - `redis-agents` → `agent-redis-seeder` → 업무 에이전트 순으로 기동됩니다.
   - `redis-iam`은 프론트엔드와 정책 서버가 공유합니다.
3. 주요 접속 포인트
   - IAM UI: http://localhost:8006
   - 정책 서버 헬스체크: http://localhost:8005/health
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
  - 기본 데이터는 `frontend/database.py` 초기화 로직으로 적재 (에이전트/룰셋/정책/로그 키)
  - 프론트엔드에서 CRUD 수행 시 즉시 Redis에 반영

## 6. 주요 코드/모듈 설명
- `frontend/app.py`
  - Flask Blueprints 없이 단일 앱으로 `/dashboard`, `/agents`, `/ruleset`, `/logs` 페이지 제공
  - `/api/graph/agent-flow`, `/api/stats/overview` 등 데이터 엔드포인트 포함
  - Redis 커넥션은 `frontend/database.get_db()`를 통해 주입
- `frontend/database.py`
  - IAM Redis 헬퍼 (에이전트, 룰셋, 정책, 로그 CRUD + 통계)
  - 새 인스턴스 생성 시 기본 데이터 자동 세팅 → Docker 로컬 환경에서 초기 화면 보장
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

## 10. 커뮤니케이션 및 향후 작업 메모
- 프론트엔드 레이아웃은 국문화된 상태이며, 추가 컴포넌트 개발 시 동일한 그리드/폰트 규칙 유지 필요 (`frontend/style.css` 참고)
- Gemini API 키는 실제 운영 시 Secret Manager나 Vault 연동 고려
- 로그 고도화(예: ElasticSearch 연동) 및 IAM 정책 스키마 버전 관리가 후속 과제로 남아 있음
- Kubernetes 이전을 고려할 경우, Redis 2종을 각기 StatefulSet으로 구성하고 시드 잡(CronJob) 분리 권장

---
이 문서는 새로운 에이전트나 개발자가 빠르게 환경을 이해하고 기동할 수 있도록 현재 구성과 절차를 요약합니다. 추가 질문이나 업데이트는 `ARCHITECTURE.md`, `DOCKER_GUIDE.md`, `README.md`를 참고하거나 최신 변경 사항 커밋 메시지를 확인하세요.
