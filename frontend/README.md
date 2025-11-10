# IAM Management Frontend

Flask 기반 IAM 정책 관리 및 시각화 도구입니다.

## 주요 기능

### 1. Dashboard (대시보드)
- 전체 시스템 현황 조회
- 에이전트 상태 모니터링
- 최근 정책 위반 통계
- 실시간 이벤트 로그

### 2. Agents (에이전트 관리)
- 에이전트 목록 조회
- 에이전트별 IAM 정책 설정
- 정책 할당 및 수정

### 3. Ruleset (룰셋 관리)
- 프롬프트 검증 룰셋 CRUD
- 툴 검증 룰셋 CRUD
- 응답 필터링 룰셋 CRUD
- 룰셋 활성화/비활성화

### 4. Logs (로그 모니터링)
- 정책 위반 로그 조회
- 에이전트별 필터링
- 타임라인 기반 검색

## 데이터베이스 구조 (Redis)

### Keys

#### Agents
- `agents:all` (Set) - 모든 에이전트 ID 목록
- `agents:{agent_id}` (Hash) - 에이전트 정보

#### Rulesets
- `rulesets:all` (Set) - 모든 룰셋 ID 목록
- `rulesets:{ruleset_id}` (Hash) - 룰셋 정보

#### Policies
- `policies:all` (Set) - 모든 정책 ID 목록
- `policies:{policy_id}` (Hash) - 정책 정보

#### Logs
- `logs:all` (List) - 로그 엔트리 (최신 10000개)

## 로컬 실행

```bash
# IAM 솔루션 전용 Redis 실행 (포트 6380 사용)
docker run -d -p 6380:6379 --name attager-redis-iam redis:7-alpine

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python app.py
```

**주의**: 에이전트용 Redis (6379)와 IAM 솔루션용 Redis (6380)는 완전히 분리되어 있습니다.

브라우저에서 `http://localhost:8006` 접속

## Docker 실행

```bash
# Attager 폴더에서
docker-compose up -d redis frontend

# 또는 전체 시스템
docker-compose up -d
```

- Frontend UI: `http://localhost:8006`
- Policy Server API: `http://localhost:8005`

## API 엔드포인트

### Agents
- `GET /api/agents` - 모든 에이전트 조회
- `GET /api/agents/{agent_id}` - 특정 에이전트 조회
- `POST /api/agents` - 에이전트 생성
- `PUT /api/agents/{agent_id}` - 에이전트 수정

### Rulesets
- `GET /api/rulesets` - 모든 룰셋 조회
- `GET /api/rulesets/{ruleset_id}` - 특정 룰셋 조회
- `POST /api/rulesets` - 룰셋 생성
- `PUT /api/rulesets/{ruleset_id}` - 룰셋 수정
- `DELETE /api/rulesets/{ruleset_id}` - 룰셋 삭제

### Policies
- `GET /api/policies` - 모든 정책 조회
- `GET /api/policies/{policy_id}` - 특정 정책 조회
- `POST /api/policies` - 정책 생성
- `PUT /api/policies/{policy_id}` - 정책 수정

### IAM (에이전트용)
- `GET /api/iam/policy/{agent_id}` - 에이전트 정책 조회 (enriched)

### Logs
- `GET /api/logs?limit=100&agent_id=orchestrator` - 로그 조회
- `POST /api/logs` - 로그 추가
- `DELETE /api/logs` - 로그 삭제

### Health
- `GET /health` - 헬스 체크

## 기존 server.py 대체

이 Flask 앱은 기존 `Orchestrator_plugin/server.py`의 모든 기능을 포함하며, 추가로 시각화 및 관리 UI를 제공합니다.

에이전트들은 `POLICY_SERVER_URL` 환경 변수를 통해 이 서버에 연결됩니다.

## 환경 변수

- `REDIS_HOST` - Redis 호스트 (기본값: localhost)
- `REDIS_PORT` - Redis 포트 (기본값: 6379)
- `PORT` - 서버 포트 (기본값: 8006)

