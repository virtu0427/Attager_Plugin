# Dockerfile for Policy Server
FROM python:3.11-slim

WORKDIR /app

# Copy shared requirements
COPY requirements.txt ./requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy server files
COPY Orchestrator_plugin/server_redis.py .

# Copy IAM security solution modules
COPY iam ./iam

# Copy frontend compatibility wrapper
COPY frontend/database.py ./frontend/
RUN touch ./frontend/__init__.py

EXPOSE 8005

CMD ["python", "server_redis.py"]
