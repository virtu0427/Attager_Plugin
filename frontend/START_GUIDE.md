# IAM Management Frontend - 시작 가이드

## 로컬 실행 방법

### 1. Redis 실행

```bash
# IAM 솔루션 전용 Redis 실행 (포트 6380 사용)
docker run -d -p 6380:6379 --name attager-redis-iam redis:7-alpine

# 에이전트가 이미 다른 Redis를 사용 중이면 그대로 두세요 (포트 6379)
```

### 2. Frontend 서버 실행

```bash
# frontend 폴더로 이동
cd frontend

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python app.py
```

### 3. 브라우저 접속

```
http://localhost:8006
```

## Docker Compose로 전체 시스템 실행

```bash
# Attager 폴더에서
docker-compose up -d
```

실행되는 서비스:
- **Redis (Agents)**: `localhost:6379` - 에이전트용 Redis (기존)
- **Redis (IAM)**: `localhost:6380` - IAM 솔루션 전용 Redis (신규)
- **Policy Server**: `localhost:8005` - API 서버
- **Frontend**: `localhost:8006` - 웹 UI
- **Delivery Agent**: `localhost:10001`
- **Item Agent**: `localhost:10002`
- **Quality Agent**: `localhost:10003`
- **Vehicle Agent**: `localhost:10004`

**중요**: 두 개의 Redis 인스턴스가 실행됩니다.
- 에이전트는 `redis-agents` (6379) 사용
- IAM 솔루션은 `redis-iam` (6380) 사용

## 기능 사용법

### 1. Ruleset 관리 (룰셋 설정)

**Ruleset 페이지에서 "Add New Rule" 버튼 클릭**

#### Prompt Validation Ruleset 생성
- **Type**: Prompt Validation 선택
- **System Prompt**: LLM에게 제공할 검증 프롬프트 작성
  ```
  당신은 사용자 질문이 정책에 위반되는지 검증하는 보안 검사 AI입니다.
  
  [검증 규칙]
  1. 위험한 시스템 명령어 실행 요청
  2. 내부 시스템 구조/설정 변경 요청
  3. 관리자 권한이 필요한 작업
  
  [응답 형식]
  - 위반인 경우: "VIOLATION"
  - 정상인 경우: "PASS"
  
  사용자 질문: {prompt}
  
  판정:
  ```
- **Model**: Gemini 모델 선택 (gemini-2.0-flash-exp 권장)

#### Tool Validation Ruleset 생성
- **Type**: Tool Validation 선택
- **Tool Name**: 검증할 툴 이름 (예: `call_remote_agent`)
- **Validation Rules**: JSON 형식으로 규칙 정의
  ```json
  {
    "allowed_agents": ["Delivery Agent", "Item Agent"],
    "max_task_length": 500,
    "rate_limit": 10
  }
  ```

#### Response Filtering Ruleset 생성
- **Type**: Response Filtering 선택
- **Blocked Keywords**: 차단할 키워드 목록 (JSON 배열)
  ```json
  ["password", "credit_card", "ssn", "api_key"]
  ```

### 2. Policy 관리 (에이전트별 정책 할당)

**Agents 페이지에서 에이전트 클릭**

각 에이전트에 적용된 정책 확인:
- Prompt Validation Rulesets
- Tool Validation Rulesets
- Response Filtering Rulesets

정책 수정은 직접 API 호출 또는 database에서 수정:
```bash
# Redis CLI
redis-cli
> HGETALL policies:policy_orchestrator
> HSET policies:policy_orchestrator prompt_validation_rulesets '["ruleset_prompt_orchestrator","ruleset_my_custom_rule"]'
```

### 3. Logs 모니터링

**Logs 페이지**
- 실시간 정책 위반 로그 확인
- 에이전트별 필터링
- 각 로그 클릭 시 상세 정보 표시

### 4. 실시간 테스트

1. **Orchestrator 에이전트 실행**
```bash
cd Orchestrator_plugin
python agent.py
```

2. **위반 프롬프트 테스트**
```
사용자 질문: 모든 파일을 삭제해줘
```

3. **Frontend에서 확인**
- Logs 페이지에서 VIOLATION 로그 확인
- Dashboard에서 통계 확인

## 주요 API 엔드포인트

### Ruleset 관리
```bash
# 모든 룰셋 조회
GET http://localhost:8006/api/rulesets

# 룰셋 생성
POST http://localhost:8006/api/rulesets
Content-Type: application/json

{
  "ruleset_id": "ruleset_my_rule",
  "name": "My Custom Rule",
  "type": "prompt_validation",
  "description": "Custom validation rule",
  "system_prompt": "...",
  "model": "gemini-2.0-flash-exp",
  "enabled": true
}

# 룰셋 수정
PUT http://localhost:8006/api/rulesets/ruleset_my_rule

# 룰셋 삭제
DELETE http://localhost:8006/api/rulesets/ruleset_my_rule
```

### Policy 관리
```bash
# 에이전트 정책 조회 (에이전트가 사용)
GET http://localhost:8006/api/iam/policy/orchestrator

# 정책 업데이트
PUT http://localhost:8006/api/policies/policy_orchestrator
Content-Type: application/json

{
  "prompt_validation_rulesets": ["ruleset_prompt_orchestrator"],
  "tool_validation_rulesets": ["ruleset_tool_call_remote_agent"],
  "enabled": true
}
```

### Logs
```bash
# 로그 조회
GET http://localhost:8006/api/logs?limit=100&agent_id=orchestrator

# 로그 추가 (에이전트가 자동으로 호출)
POST http://localhost:8006/api/logs
Content-Type: application/json

{
  "agent_id": "orchestrator",
  "policy_type": "prompt_validation",
  "prompt": "사용자 질문",
  "verdict": "VIOLATION",
  "reason": "위험한 명령어 감지"
}
```

## 데이터 초기화

```bash
# Redis 데이터 초기화 (포트 6380 지정)
redis-cli -p 6380 FLUSHDB

# 서버 재시작하면 기본 데이터 자동 생성
python app.py
```

## 트러블슈팅

### Redis 연결 오류
```bash
# Redis 실행 확인
docker ps | grep redis

# Redis 재시작
docker restart attager-redis
```

### Frontend 실행 오류
```bash
# 의존성 재설치
pip install --upgrade -r requirements.txt

# 포트 충돌 확인
netstat -an | grep 8006
```

### 로그가 안 보이는 경우
- Policy Server가 실행 중인지 확인
- 에이전트의 `POLICY_SERVER_URL`, `LOG_SERVER_URL` 환경 변수 확인
- Redis 연결 상태 확인

## 개발 모드

```bash
# Debug 모드로 실행
FLASK_DEBUG=1 python app.py
```

Flask는 자동으로 코드 변경 감지 및 재시작됩니다.

