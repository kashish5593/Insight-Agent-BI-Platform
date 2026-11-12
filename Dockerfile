FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies separately to improve Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source and its seed data.
COPY . .

EXPOSE 8000 8501

# Compose overrides the command for the API and dashboard services.
CMD ["python", "run_pipeline.py"]
