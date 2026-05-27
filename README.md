# Smart Surveillance System with OpenCV

A modern, full-stack intelligent surveillance application that leverages OpenCV for real-time video analysis, motion detection, and object recognition. Built with TypeScript (82.6%), Python (14.2%), and styled with CSS.

![TypeScript](https://img.shields.io/badge/TypeScript-82.6%25-blue)
![Python](https://img.shields.io/badge/Python-14.2%25-green)
![CSS](https://img.shields.io/badge/CSS-2.3%25-purple)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-Active-brightgreen)

## 🎯 Features

- **Real-Time Video Processing**: Stream and analyze video feeds using OpenCV
- **Motion Detection**: Intelligent motion detection with configurable sensitivity
- **Object Recognition**: AI-powered object detection and tracking
- **Web Dashboard**: Modern, responsive TypeScript/React frontend
- **REST API**: FastAPI backend with full REST endpoints
- **Telegram Alerts**: Optional real-time notifications for detected events
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **GPU Acceleration**: Support for NVIDIA GPU acceleration
- **Database Persistence**: SQLite database for event storage
- **Multi-Camera Support**: Handle multiple camera sources (Webcam, RTSP streams)

## 📋 Prerequisites

- **Docker Desktop** (or Docker + Docker Compose)
- **Node.js** 18+ (for local frontend development)
- **Python** 3.10+ (for local backend development)
- **(Optional) NVIDIA Container Toolkit** (for GPU support)

## 🚀 Quick Start

### Using Docker (Recommended)

#### 1. **CPU-Based Deployment**

```bash
# Clone the repository
git clone https://github.com/Shyam-2315/Smartsurvillence_System_OpenCV.git
cd Smartsurvillence_System_OpenCV

# Build and run with Docker Compose
docker compose up --build
```

Access the application:
- **Frontend**: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- **Backend API Docs**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

#### 2. **GPU-Accelerated Deployment** (Linux with NVIDIA GPU)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

#### 3. **Webcam Access on Linux**

```bash
docker compose -f docker-compose.yml -f docker-compose.webcam.linux.yml up --build
```

### Optional: Telegram Alerts

Create a `.env` file in the repository root:

```env
BOT_TOKEN=your_bot_token_here
CHAT_ID=your_chat_id_here
```

Or set environment variables:

```bash
export BOT_TOKEN=123456:ABC...
export CHAT_ID=123456789
docker compose up --build
```

## 📁 Project Structure

```
Smartsurvillence_System_OpenCV/
├── frontend/                   # TypeScript/React frontend
│   ├── src/                   # React components and pages
│   ├── package.json           # Frontend dependencies
│   └── Dockerfile             # Frontend container config
├── backend/                    # Python FastAPI backend
│   ├── main.py                # FastAPI application
│   ├── surveillance.db        # SQLite database
│   ├── Dockerfile             # Backend container config
│   └── requirements.txt        # Python dependencies
├── outputs/                    # Captured images/videos
├── docker-compose.yml          # Main Docker Compose file
├── docker-compose.gpu.yml      # GPU acceleration configuration
├── docker-compose.webcam.linux.yml  # Linux webcam passthrough
├── README.md                   # This file
└── README_DOCKER.md           # Docker-specific documentation
```

## 🛠️ Technology Stack

### Frontend
- **Framework**: React 19 with TanStack Start
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Radix UI (fully accessible)
- **State Management**: TanStack Router & React Query
- **Routing**: TanStack Router
- **Forms**: React Hook Form with Zod validation
- **Charts**: Recharts
- **HTTP Client**: Axios
- **Animations**: Framer Motion

### Backend
- **Framework**: FastAPI (Python)
- **Video Processing**: OpenCV
- **Database**: SQLite
- **Notifications**: Telegram Bot API
- **Task Processing**: Background workers

### DevOps
- **Containerization**: Docker & Docker Compose
- **GPU Support**: NVIDIA Container Toolkit

## 📖 API Documentation

Once the backend is running, access the interactive API documentation at:

```
http://127.0.0.1:8001/docs
```

This provides a Swagger UI where you can test all available endpoints.

## 🎮 Usage

### Web Dashboard

1. Open [http://127.0.0.1:3000](http://127.0.0.1:3000) in your browser
2. Configure your camera source (webcam or RTSP URL)
3. Start the surveillance stream
4. Monitor detections in real-time
5. View historical events and captured footage

### Camera Configuration

#### Webcam (Local)
- **Windows/macOS**: Docker Desktop doesn't directly support `/dev/video0`
  - Recommended: Use an RTSP camera source instead
  - Or: Configure the app with `CAMERA_SOURCE=/dev/video0` if supported

- **Linux**: Use the webcam Linux Compose file:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.webcam.linux.yml up --build
  ```

#### IP/RTSP Camera
```env
CAMERA_SOURCE=rtsp://your-camera-url:port/stream
```

## 🔧 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `BOT_TOKEN` | Telegram Bot API Token | Empty | Optional |
| `CHAT_ID` | Telegram Chat ID for alerts | Empty | Optional |
| `VITE_API_BASE_URL` | Backend API URL (Frontend) | `http://backend:8001` | No |
| `CAMERA_SOURCE` | Camera input source | Webcam | No |

## 📦 Local Development

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The API will be available at `http://localhost:8001`

## 🐛 Troubleshooting

### Issue: Container won't start
- Check Docker daemon is running: `docker ps`
- View logs: `docker compose logs -f`
- Rebuild: `docker compose up --build`

### Issue: API not accessible from frontend
- Verify backend is running: `docker ps`
- Check port 8001 is not in use: `lsof -i :8001`
- Review `VITE_API_BASE_URL` environment variable

### Issue: Camera not detected
- **Windows/macOS**: Use RTSP camera URL (Docker limitation)
- **Linux**: Use the webcam Linux Compose file
- Verify camera permissions: `ls -la /dev/video0`

### Issue: GPU not being used
- Verify NVIDIA Docker support: `docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi`
- Use GPU Compose file: `docker-compose.gpu.yml`

## 📝 Database

The application uses SQLite for persistent storage:
- **Location**: `./backend/surveillance.db`
- **Data**: Events, detections, alerts
- **Persistence**: Volume mount ensures data survives container restarts

## 🔐 Security Notes

- Store sensitive credentials in `.env` file (not in version control)
- `.env` is added to `.gitignore` - never commit it
- Use environment-specific configurations for production
- Consider setting up HTTPS/TLS for production deployments

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

This project is open source and available under the MIT License.

## 👤 Author

**Shyam-2315**

- GitHub: [@Shyam-2315](https://github.com/Shyam-2315)
- Repository: [Smartsurvillence_System_OpenCV](https://github.com/Shyam-2315/Smartsurvillence_System_OpenCV)

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [OpenCV Documentation](https://opencv.org/)
- [TanStack Documentation](https://tanstack.com/)

## 🐳 Docker Quick Reference

```bash
# Build the image
docker compose build

# Start services
docker compose up

# Start in background
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Stop and remove volumes
docker compose down -v

# Rebuild and start
docker compose up --build

# Run with GPU support
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

---

**Made with ❤️ for intelligent video surveillance**
