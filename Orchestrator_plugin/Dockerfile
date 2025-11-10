# Dockerfile for Policy Server
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY frontend/requirements.txt ./frontend_requirements.txt
RUN echo "fastapi>=0.104.0" > requirements.txt && \
    echo "uvicorn>=0.24.0" >> requirements.txt && \
    cat frontend_requirements.txt >> requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy server files
COPY Orchestrator_plugin/server_redis.py .

# Copy frontend database module
COPY frontend/database.py ./frontend/
RUN touch ./frontend/__init__.py

EXPOSE 8005

CMD ["python", "server_redis.py"]

