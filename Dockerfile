# 1. Base Image: Use a lightweight Python version (same as your conda env)
FROM python:3.10-slim

# 2. Set Environment Variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files
# PYTHONUNBUFFERED: Ensures logs appear immediately (crucial for Streamlit)
# PYTHONPATH: Tells Python to look inside /app/src for modules (Fixes import errors)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src"

# 3. Set Working Directory
WORKDIR /app

# 4. Install Dependencies
# We copy requirements first to leverage Docker Cache (builds faster)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Source Code
# We copy the 'src' folder into '/app/src'
#COPY src/ ./src
COPY . .

# 6. Expose the Streamlit Port
EXPOSE 8501

# 7. Healthcheck (MLOps Best Practice)
# Checks if the app is actually running every 30s
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 8. Run the App
# Streamlit handles the 'src/app.py' path because we are in /app
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]