# Multi-Agent System Docker Compose Guide

이 가이드는 전체 다중 에이전트 시스템을 Docker Compose로 실행하는 방법을 설명합니다.

## 시스템 구성

### 서비스 목록
- **Agent Registry** (포트 8000): 에이전트 카드 관리
- **Agent Registry Frontend** (포트 3000): 레지스트리 UI
- **IAM Policy Server** (포트 8005): 정책/로그 서버
- **IAM Frontend** (포트 8006): IAM 관리 UI
- **Orchestrator Plugin Agent** (포트 10000): 메인 오케스트레이터, 다른 에이전트를 조율 (Docker Compose에서 기본 포함)
- **Orchestrator Client UI** (포트 8010): 오케스트레이터 플러그인과 대화하는 독립 UI
- **Delivery Agent** (포트 10001): 배송 데이터 관리
- **Item Agent** (포트 10002): 아이템 데이터 관리
- **Quality Agent** (포트 10003): 품질 데이터 관리
- **Vehicle Agent** (포트 10004): 차량 데이터 관리
- **JWT Auth Server** (포트 8011): JWT 발급/검증용 인증 서버
- **JWS Signing Server** (포트 8012): 에이전트 카드 서명/검증용 서버

## 실행 방법

### 1. 전체 시스템 시작
루트 디렉토리(`/workspace/Attager_Plugin`)에서 아래 명령을 실행하면 오케스트레이터 플러그인 에이전트와 별도 클라이언트 UI까지 모든 서비스가 함께 올라갑니다.
```bash
# 모든 서비스 빌드 및 시작
docker-compose up --build

# 백그라운드에서 실행
docker-compose up --build -d
```

### 2. 로그 확인
```bash
# 모든 서비스 로그 보기
docker-compose logs

# 특정 서비스 로그 보기
docker-compose logs orchestrator
docker-compose logs delivery-agent
docker-compose logs redis
```

### 3. 서비스 상태 확인
```bash
# 실행 중인 컨테이너 확인
docker-compose ps

# 서비스 헬스체크
curl http://localhost:10000  # Orchestrator
curl http://localhost:10001  # Delivery Agent
curl http://localhost:10002  # Item Agent  
curl http://localhost:10003  # Quality Agent
curl http://localhost:10004  # Vehicle Agent
```

### 4. 시스템 중지
```bash
# 서비스 중지
docker-compose down

# 볼륨까지 삭제 (데이터 초기화)
docker-compose down -v
```

## 개발 환경

### 개별 서비스 재시작
```bash
# 특정 서비스만 재시작
docker-compose restart orchestrator
docker-compose restart delivery-agent
```

### 서비스 스케일링
```bash
# 에이전트 서비스 복제 (로드밸런싱)
docker-compose up --scale delivery-agent=2 --scale item-agent=2
```

### 디버깅
```bash
# 컨테이너 내부 접근
docker-compose exec orchestrator bash
docker-compose exec redis redis-cli

# 네트워크 상태 확인
docker network ls
docker network inspect other-agent_agent-network
```

## 환경 변수

각 에이전트는 다음 환경 변수를 사용합니다:
- `REDIS_HOST`: Redis 서버 호스트 (기본값: redis, Docker에서는 redis)
- `REDIS_PORT`: Redis 서버 포트 (기본값: 6379)
- `OLLAMA_HOST`: Ollama 서버 호스트 (기본값: localhost, Docker에서는 host.docker.internal)
- `GOOGLE_API_KEY`: Gemini 호출 시 사용되는 키 (없으면 로컬 LLM으로 fallback 시도)
- `AGENT_REGISTRY_URL`: 오케스트레이터 플러그인이 에이전트 카드를 조회할 레지스트리 URL (Docker에서는 `http://agent-registry:8000`)
- `POLICY_SERVER_URL` / `LOG_SERVER_URL`: IAM 정책/로그 서버 URL (Docker에서는 `http://policy-server:8005`)
- `ORCHESTRATOR_RPC_URL`: 클라이언트 UI가 오케스트레이터 플러그인에 RPC로 연결할 엔드포인트 (Docker에서는 `http://orchestrator:10000/`)
- `AGENT_INTERNAL_HOST`: 레지스트리 카드에 `localhost`가 들어 있어도 컨테이너 내부에서 접근 가능한 공통 호스트로 강제할 때 사용 (예: `host.docker.internal`). 카드 URL이 `host.docker.internal`로 등록된 경우에도 자동으로 컨테이너 서비스명으로 치환됩니다.
- `DELIVERY_AGENT_HOST` / `ITEM_AGENT_HOST` / `QUALITY_AGENT_HOST` / `VEHICLE_AGENT_HOST`: 각 포트(10001~10004)에 대응하는 서비스 이름을 덮어쓰고 싶을 때 설정. 기본값은 Compose 서비스명(`delivery-agent`, `item-agent` 등)이라 별도 설정 없이도 컨테이너 간 호출이 동작합니다.

### Ollama 서버 설정
**중요**: Docker 컨테이너에서 호스트의 Ollama 서버(포트 11434)에 접근하기 위해 `host.docker.internal`을 사용합니다.

#### 로컬 실행 시:
- Ollama는 `localhost:11434`에서 실행되어야 합니다
- 환경 변수 설정 불필요 (기본값 사용)

#### Docker 실행 시:
- Ollama는 **호스트 머신**에서 `localhost:11434`에서 실행되어야 합니다
- Docker Compose가 자동으로 `OLLAMA_HOST=host.docker.internal`을 설정합니다

## 데이터 지속성

Redis 데이터는 `./agentDB/redis-data` 디렉토리에 저장되어 컨테이너 재시작 후에도 유지됩니다.

## 네트워크 구성

모든 서비스는 `agent-network` 브리지 네트워크를 통해 통신합니다. 각 컨테이너는 서비스 이름으로 서로 접근할 수 있습니다.

## 문제 해결

### Ollama 연결 문제
Docker 컨테이너에서 호스트의 Ollama에 접근할 수 없는 경우:

1. **Ollama 서버 확인**:
   ```bash
   # 호스트에서 Ollama가 실행 중인지 확인
   curl http://localhost:11434/api/tags
   ```

2. **Ollama 외부 접근 허용**:
   ```bash
   # Ollama를 모든 인터페이스에서 수신하도록 실행
   OLLAMA_HOST=0.0.0.0 ollama serve
   ```

3. **Windows에서 host.docker.internal 문제**:
   ```yaml
   # docker-compose.yml에서 다음으로 변경 가능
   environment:
     - OLLAMA_HOST=host.docker.internal  # 또는
     - OLLAMA_HOST=host-gateway         # 또는  
     - OLLAMA_HOST=172.17.0.1          # Docker 게이트웨이 IP
   ```

### 포트 충돌
만약 포트가 이미 사용 중이라면 docker-compose.yml에서 외부 포트를 변경하세요:
```yaml
ports:
  - "11000:10000"  # 외부 포트를 11000으로 변경
```

### 빌드 문제
```bash
# 캐시 없이 완전히 새로 빌드
docker-compose build --no-cache

# 이미지 정리
docker system prune -a
```

### 의존성 문제
requirements.txt에 누락된 패키지가 있다면 해당 파일에 추가하고 다시 빌드하세요.

## API 엔드포인트

### Orchestrator Agent (포트 10000)
- 메인 진입점으로 사용자 요청을 받아 적절한 에이전트에게 위임

### 개별 Agent 엔드포인트
각 에이전트는 A2A 프로토콜을 통해 통신하며, 직접 API 호출도 가능합니다.

예시:
```bash
# Delivery 데이터 조회 요청
curl -X POST http://localhost:10001/send-message \
  -H "Content-Type: application/json" \
  -d '{"message": {"role": "user", "parts": [{"type": "text", "text": "Read delivery data for ORD1001"}]}}'
```
