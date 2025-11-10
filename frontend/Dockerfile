# Dockerfile for Frontend IAM Management UI
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all frontend files
COPY frontend/ .

EXPOSE 8006

CMD ["python", "app.py"]

