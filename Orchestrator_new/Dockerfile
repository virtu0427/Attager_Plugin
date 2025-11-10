FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from root
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy utils first
COPY utils/ ./utils/

# Copy orchestrator files
COPY Orchestrator_new/ .

# Expose port
EXPOSE 10000

# Run the agent
CMD ["python", "__main__.py", "--host", "0.0.0.0", "--port", "10000"]
