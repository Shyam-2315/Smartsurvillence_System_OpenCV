FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OpenCV runtime deps (headless still needs some libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ /app/backend/

EXPOSE 8001

# Runs FastAPI + starts camera/AI workers on startup.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
