# Python 3.9 + 최신 SQLite (bullseye에는 3.34 이상 포함)
FROM python:3.9-slim-bullseye

# 작업 디렉토리
WORKDIR /app

# 의존성 설치
COPY backend/app/requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends sqlite3 libsqlite3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

# 소스 복사
COPY backend/app/ .

# FastAPI 실행
EXPOSE 8000
ENV PYTHONPATH=/app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

