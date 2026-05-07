# Docker setup (Smart Surveillance)

## Prerequisites
- Docker Desktop
- (Optional GPU) Linux host + NVIDIA Container Toolkit

## Run (CPU)
From the repo root:

```bash
docker compose up --build
```

- Backend: `http://127.0.0.1:8001/docs`
- Frontend: `http://127.0.0.1:3000`

## Telegram alerts (optional)
Create a `.env` in repo root (or set env vars in your shell):

```env
BOT_TOKEN=123456:ABC...
CHAT_ID=123456789
```

## Run with GPU (later)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

## Notes about camera access
- On **Windows/macOS (Docker Desktop)**, direct webcam passthrough does **not** use `/dev/video0`.
  Recommended: use an **RTSP/IP camera** input (we can add `CAMERA_SOURCE=rtsp://...`).
- On **Linux**, enable webcam passthrough with:

```bash
docker compose -f docker-compose.yml -f docker-compose.webcam.linux.yml up --build
```

