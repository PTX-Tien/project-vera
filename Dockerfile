# 1. Base Image
FROM python:3.10-slim

# 2. System Dependencies
# libgomp1 is CRITICAL for FAISS (Vector DB) to work on slim images
# curl is needed for the HEALTHCHECK command
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Environment Variables
# PYTHONPATH="/app/src" allows us to run "uvicorn api:app" directly
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src"

# 4. Set Working Directory
WORKDIR /app

# 5. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy Source Code
COPY . .

# 7. Expose FastAPI Port
EXPOSE 8000

# 8. Healthcheck
# Hits the /health endpoint we created in api.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl --fail http://localhost:8000/health || exit 1

# 9. Start the Server
# We use 'api:app' because /app/src is in the PYTHONPATH
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]