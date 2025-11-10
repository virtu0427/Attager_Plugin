# Multi-Agent System Docker Compose Guide

이 가이드는 전체 다중 에이전트 시스템을 Docker Compose로 실행하는 방법을 설명합니다.

## 시스템 구성

### 서비스 목록
- **Redis Database** (포트 6379): 데이터 저장소
- **Orchestrator Agent** (포트 10000): 메인 오케스트레이터, 다른 에이전트들을 조율
- **Delivery Agent** (포트 10001): 배송 데이터 관리
- **Item Agent** (포트 10002): 아이템 데이터 관리  
- **Quality Agent** (포트 10003): 품질 데이터 관리
- **Vehicle Agent** (포트 10004): 차량 데이터 관리

## 실행 방법

### 1. 전체 시스템 시작
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
