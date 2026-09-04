# Smart Surveillance System

FastAPI, React/Vite, OpenCV and YOLO surveillance application with shared live video processing, tracking, loitering alerts, configurable zones, SQLite incident history, evidence images and optional Telegram notifications.

## Architecture

`Camera source -> one reconnecting camera worker -> one YOLO/tracking worker -> MJPEG /video + REST API -> React dashboard`

The AI pipeline is shared: opening several dashboard tabs does not start additional YOLO workers. Screenshots belong in `outputs/` locally, or the Docker `surveillance_data` volume.

## Requirements

- Windows 10/11: Python 3.11+, Node.js 18+, PowerShell. A local webcam is supported by the local backend.
- Docker: Docker Desktop for RTSP/network-camera or server deployment. Windows Docker webcam passthrough is not a supported workflow.
- An RTSP URL or a camera visible to OpenCV.

## Windows setup and webcam run

From the repository root, install once:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

Use two PowerShell terminals:

```powershell
.\scripts\start_backend.ps1
```

```powershell
.\scripts\start_frontend.ps1
```

Equivalent backend command (the README does **not** use `python main.py`):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn api:app --host 127.0.0.1 --port 8001
```

The dashboard is normally at http://localhost:5173 and Swagger API documentation is http://127.0.0.1:8001/docs.

## Configuration

Copy `.env.example` to `.env` and edit it. `.env` is ignored by Git.

```env
CAMERA_SOURCE=0
# CAMERA_SOURCE=rtsp://username:password@192.168.1.50:554/stream1
YOLO_MODEL=backend/yolov8n.pt
CONFIDENCE_THRESHOLD=0.5
TELEGRAM_ENABLED=false
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

`CAMERA_SOURCE=0` (or `1`) selects a local camera. Numeric strings are converted to indexes and use OpenCV's DirectShow backend on Windows when available; all other values are passed to OpenCV unchanged as RTSP URLs or video file paths, so RTSP is never forced through DirectShow. The source is redacted in `/status` so RTSP credentials are never returned. If unavailable, the API remains online and retries the camera periodically.

Set `TELEGRAM_ENABLED=true`, `BOT_TOKEN`, and `CHAT_ID` only when notifications are needed. Tokens and RTSP passwords must never be committed.

## Docker / RTSP deployment

Set `CAMERA_SOURCE` and any Telegram values in `.env`, then run:

```powershell
docker compose up --build -d
docker compose logs -f
```

Dashboard: http://127.0.0.1:3000. API: http://127.0.0.1:8001/docs.

In Docker, nginx exposes port 3000 and the frontend uses `VITE_API_BASE_URL=/api`; `backend:8001` remains Docker-only DNS and is never sent to browser JavaScript. Persistent SQLite data and captures are kept in the named `surveillance_data` volume.

### Deployment paths

1. **Windows local webcam** — recommended for laptop/demo use. Run FastAPI natively with `CAMERA_SOURCE=0`; Docker Desktop is not a dependable Windows-webcam passthrough.
2. **RTSP/IP camera** — use an RTSP URL in `.env`; FastAPI reconnects without exiting when a stream is unavailable.
3. **Docker + RTSP** — compose puts nginx on port 3000. The browser uses same-origin `/api`; nginx forwards it to FastAPI and disables buffering for the MJPEG stream.
4. **Internet-facing** — requires a real TLS reverse proxy, `AUTH_ENABLED=true`, `PROTECT_MONITORING_ROUTES=true`, `COOKIE_SECURE=true`, strong secrets, restricted CORS, and firewall rules. This repository does not provide certificates or a public-domain deployment.

For a TLS terminator, use placeholder certificate paths only; do not commit keys:

```nginx
server {
  listen 443 ssl;
  server_name surveillance.example.com;
  ssl_certificate /etc/nginx/certs/fullchain.pem;
  ssl_certificate_key /etc/nginx/certs/privkey.pem;
  # Proxy / to the compose nginx service; retain its /api and /video rules.
}
```

Nginx applies a small per-IP limit to `/api/auth/login` (5 requests/minute plus a five-request burst). For Internet exposure, pair it with edge/WAF rate limiting.

## API

- `GET /health` — process health.
- `GET /ready` — API readiness plus camera/AI state.
- `GET /status` — configured (redacted) camera source, reconnect state, AI, CUDA and Telegram state.
- `GET /video` — MJPEG processed stream.
- `/incidents`, `/zones`, `/rules/loitering`, `/images` — dashboard data and configuration.
- `/visual-intelligence` — protected Visual Intelligence V1 evidence analysis.
- `/airborne/missions` — Phase 1 mission, event, and immutable-evidence metadata foundation (no MAVLink or recorded-video upload yet).

## Visual Intelligence V1

Visual Intelligence is an additive, non-biometric investigation workspace. Originals are immutable; enhancements, overlays, and region crops are separate derivatives under `outputs/visual_intelligence/`. OCR uses EasyOCR on CPU. Its model cache is `outputs/visual_intelligence/models/easyocr`; `OCR_MODEL_DOWNLOAD_ENABLED=false` prevents automatic model downloads, so install the recognition/detection model into that cache during deployment or temporarily set it true for one controlled initialization. Web Intelligence is disabled by default; configure `WEB_SEARCH_ENABLED=true`, `WEB_SEARCH_PROVIDER=brave`, and `WEB_SEARCH_API_KEY` for Brave API metadata results. The platform does not perform face recognition, reverse-face search, or identity lookup.

## Recorded Mission Analysis

Recorded missions are uploaded as immutable originals, then analyzed in a bounded in-process background queue. The worker samples frames at `RECORDED_ANALYSIS_SAMPLE_FPS`, uses the already-loaded shared YOLO model and inference lock, groups continuous class detections with `RECORDED_EVENT_MERGE_GAP_SECONDS`, and saves only representative evidence frames. It does not automatically run OCR or Web Intelligence. Analysts can explicitly open an evidence frame in Visual Intelligence.

The Recorded Missions page provides upload, progress, native replay, event timeline, evidence gallery, factual summary, and a map view when genuine GPS-track/evidence coordinates exist. `GET /airborne/missions/{id}/report` returns a structured `report_version` payload (mission, video metadata, events, evidence, analyses, and track) intended for a later PDF/export renderer; no PDF is generated by the backend today.

## Airborne Intelligence and MAVLink

The Airborne Command Center reuses the same shared `/video` MJPEG pipeline as fixed-camera monitoring. It supports fixed or airborne camera configuration; it does not create a second capture or YOLO worker. Live mission controls are mission-state metadata only and send no aircraft commands.

MAVLink is receive-only. For ArduPilot SITL, set `AIRBORNE_ENABLED=true`, `MAVLINK_ENABLED=true`, `MAVLINK_CONNECTION=udpin:127.0.0.1:14551`, `MAVLINK_SIMULATION_MODE=true`, and retain `MAVLINK_READ_ONLY=true`. `udpin:` is the pymavlink listener form: configure SITL/Mission Planner to send MAVLink UDP telemetry to port 14551. The background receiver processes HEARTBEAT, GLOBAL_POSITION_INT, GPS_RAW_INT, VFR_HUD, SYS_STATUS, ATTITUDE, and optional BATTERY_STATUS messages. It reconnects without blocking FastAPI, samples genuine GPS-bearing telemetry at the configured persistence interval, and associates it with the active live mission. `/airborne/status` reports `CONNECTING`, `CONNECTED`, `STALE`, `DISCONNECTED`, or `RECONNECTING` and exposes `simulation`/`telemetry_source`; the UI prominently labels SITL as `SIMULATION`.

Live capture uses the shared processed frame and attaches GPS only when the nearest received telemetry lies within `AIRBORNE_TELEMETRY_ASSOCIATION_MAX_SECONDS`; stale coordinates are intentionally omitted. Capture-to-Visual-Intelligence is explicit and does not send coordinates or imagery to Brave Search.

### Mission-planner coexistence and future hardware

QGroundControl, Mission Planner, or a future Pixhawk/3DR radio link can publish telemetry to the configured MAVLink UDP endpoint. This application observes telemetry only: it does not arm, change modes, upload missions, write parameters, or transmit MAVLink commands. Flight planning, RC safety, geofencing, and hardware failsafes remain the responsibility of the flight-control stack and operator.

### Phase 10: Pixhawk 2.4.8 + 3DR telemetry (bench test only)

Keep propellers removed and the aircraft stationary. VAYU-X is a telemetry observer, not a ground-control station: do not use it to arm, set modes, calibrate, upload a mission, or operate motors.

Use one serial-port owner. The preferred Windows arrangement is:

```text
Pixhawk TELEM1 -> 3DR Air radio ~RF~ 3DR Ground radio -> USB COMx
                                                       -> MAVLink forwarder/router
                                                          -> UDP -> Mission Planner
                                                          -> UDP -> VAYU-X (udpin:127.0.0.1:14551)
```

Do not open `COMx` directly in both Mission Planner and VAYU-X. A MAVLink router/forwarder that owns `COMx` and emits separate local UDP outputs avoids serial-port contention. Configure one output for Mission Planner and one for VAYU-X; set VAYU-X's `MAVLINK_CONNECTION` to the listener matching its UDP output (normally `udpin:127.0.0.1:14551`). If your installed Mission Planner provides MAVLink UDP forwarding, it may own `COMx` and forward a separate UDP stream to port 14551; confirm its version's forwarding UI and destination before relying on it. VAYU-X does not include a custom router.

For a temporary direct serial bench test only, set the detected Windows port explicitly, for example `MAVLINK_CONNECTION=COM7`; never copy that example blindly and do not start Mission Planner on the same port. Valid settings are:

```dotenv
AIRBORNE_ENABLED=true
MAVLINK_ENABLED=true
MAVLINK_SIMULATION_MODE=false
MAVLINK_CONNECTION=udpin:127.0.0.1:14551
MAVLINK_READ_ONLY=true
MAVLINK_HEARTBEAT_TIMEOUT_SECONDS=5
MAVLINK_RECONNECT_SECONDS=3
MAVLINK_DISCONNECT_SECONDS=15
```

In real mode the dashboard displays `Aircraft: PIXHAWK`, `Simulation: NO`, the heartbeat system/component IDs, armed state, and flight mode. A valid GPS fix is still required before a coordinate is accepted: no-fix/zero coordinates remain `--`. A stopped forwarder or disconnected ground radio transitions from `CONNECTED` to `STALE` after the heartbeat timeout and `DISCONNECTED` after `MAVLINK_DISCONNECT_SECONDS`; a socket failure shows `RECONNECTING`. Restoring the stream requires no VAYU-X restart and the next heartbeat returns it to `CONNECTED`.

#### Manual hardware checklist

1. Remove propellers; secure the aircraft on a bench. Do not arm or operate motors.
2. Power the Pixhawk from an appropriate bench-safe power source and confirm its normal LEDs.
3. Connect the correctly pinned TELEM1 cable to the 3DR Air radio; power the radio only as required by the approved wiring.
4. Power the 3DR Ground radio and connect it by USB to Windows.
5. In Windows Device Manager, identify the newly assigned `COMx`; do not assume `COM7`.
6. Start the forwarder/router (or Mission Planner forwarding workflow) as the sole owner of `COMx`; verify Mission Planner receives telemetry.
7. Configure a distinct UDP output to `127.0.0.1:14551` for VAYU-X, then set the environment values above and start VAYU-X.
8. On `/airborne`, verify `TELEMETRY: CONNECTED`, `Aircraft: PIXHAWK`, `Simulation: NO`, non-null system/component IDs, flight mode, armed state, battery, and attitude where emitted.
9. Check GPS indoors/outdoors as appropriate. Until the Pixhawk reports a valid fix, confirm latitude/longitude stay `--`; do not fly to obtain a fix.
10. Start and end a VAYU-X live mission while connected, wait for the configured sampling interval, and verify its persisted telemetry/track through the mission track view. A stationary aircraft can legitimately produce repeated coordinates.
11. Stop forwarding or unplug the ground radio: verify `CONNECTED` then `STALE`; on socket loss expect `RECONNECTING`. Restore the link and verify the next heartbeat returns `CONNECTED`, without restarting the backend.

### Phase 11: real airborne video link (bench test only)

The existing single OpenCV capture owner and shared YOLO worker support the ground-received airborne source directly. Do not create a second capture pipeline. Configure the receiver as either a Windows USB capture index or an RTSP/IP URL:

```dotenv
CAMERA_ID=AIR-01
CAMERA_NAME=VAYU-X
CAMERA_MODE=airborne
CAMERA_SOURCE=1
# or CAMERA_SOURCE=rtsp://receiver.example/stream
```

Existing `CAMERA_SOURCE=0`, other numeric USB indexes, and RTSP URLs remain supported. For USB discovery, with the project backend environment active run `backend\.venv\Scripts\python.exe scripts\list_cameras.py --max-index 8`. For either transport, test opening, resolution, reported FPS, and measured frame acquisition without starting YOLO using `backend\.venv\Scripts\python.exe scripts\test_video_source.py 1` or `backend\.venv\Scripts\python.exe scripts\test_video_source.py "rtsp://..."`.

The Airborne dashboard's Video field reflects the capture worker state: `CONNECTING`, `CONNECTED`, `DEGRADED`, `DISCONNECTED`, or `RECONNECTING`. Its FPS is the measured backend YOLO processing FPS, while frame age, `last_frame_at` (`last_frame_ts` in the API), and reconnect count come from the capture worker. It does not estimate radio latency, RSSI, or any unavailable link metric. Video and MAVLink run in separate workers: disconnecting the receiver must not affect telemetry status.

With an active live mission, the mission monitor records `video_lost` and `video_restored` events when the receiver changes availability. `POST /airborne/capture` (and the retained `/airborne/live/capture`) creates immutable SHA-256 evidence from the existing processed frame, attaches `AIR-01` and the active mission when present, and only correlates GPS when a fresh telemetry sample exists. The captured evidence can then be opened in Visual Intelligence for the existing enhancement, OCR, ROI, and object-analysis workflow.

Bench checklist: keep the aircraft stationary; power the camera and video transmitter/receiver according to their manuals; connect the receiver to USB or network; run the source probe; configure the values above; start VAYU-X; verify `Video: CONNECTED`, a real processing FPS, and YOLO overlay in `/video`; verify telemetry independently reports `CONNECTED`; capture an evidence frame; temporarily remove the receiver/network input and confirm a video-loss event without a telemetry loss; restore it and confirm the video-restored event. No flight is required.

### Phase 12: Raspberry Pi 5 companion (read-only, bench test only)

`companion/` is a separate lightweight Python package for the onboard Pi. The Windows FastAPI/React command center remains on the ground laptop; Visual Intelligence, web search, report generation, and the existing heavyweight YOLO pipeline do not run on the Pi. The companion only monitors Pixhawk TELEM2 MAVLink, collects local health, optionally checks camera reachability, writes bounded logs, and forwards metadata. It contains no arming, mode, mission, servo, or parameter-control functionality.

On Raspberry Pi OS, install Python and serial access, then deploy the package:

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip
sudo usermod -aG dialout $USER
mkdir -p /opt/vayu-companion && cd /opt/vayu-companion
# copy the companion directory from this project here
python3 -m venv .venv
.venv/bin/pip install -r companion/requirements.txt
```

Copy [companion/.env.example](companion/.env.example) to `/etc/vayu-companion.env` with restrictive permissions (`sudo chmod 600`):

```dotenv
COMPANION_AIRCRAFT_ID=AIR-01
COMPANION_MAVLINK_CONNECTION=/dev/serial0
COMPANION_MAVLINK_BAUD=57600
COMPANION_MAVLINK_READ_ONLY=true
COMPANION_HEALTH_INTERVAL_SECONDS=5
COMPANION_TRANSPORT=http
COMPANION_GROUND_HEALTH_URL=http://GROUND-LAPTOP:8001/companion/health/AIR-01
COMPANION_GROUND_DEVICE_KEY=replace-with-a-dedicated-device-key
COMPANION_LOG_FILE=/var/log/vayu-companion/companion.log
```

`/dev/serial0` is only an example: set the actual Pi UART device and Pixhawk TELEM2 baud to matching values. Enable the serial UART in Raspberry Pi configuration, disable the serial login shell, and use correct voltage-level/pin wiring; do not connect or control motors for this bench test. For UDP bench forwarding instead, set `COMPANION_TRANSPORT=udp`, `COMPANION_UDP_HOST`, and `COMPANION_UDP_PORT`; the transport interface intentionally does not assume Wi-Fi or any final aircraft radio technology.

On the laptop, configure `COMPANION_HEALTH_ENABLED=true` and the same `COMPANION_HEALTH_API_KEY`; this dedicated key is accepted only by `POST /companion/health/{aircraft_id}` and is never logged. It is not an admin JWT. Install [vayu-companion.service](companion/systemd/vayu-companion.service) to `/etc/systemd/system/`, then run `sudo systemctl daemon-reload`, `sudo systemctl enable --now vayu-companion`, and inspect `journalctl -u vayu-companion`. The service uses `Restart=on-failure` with a 10-second delay; the companion watchdog reports forwarding health and never reboots the Pi. Logs rotate at 2 MB with three backups by default, avoiding SD-card exhaustion.

The forwarded payload has an ISO-8601 timestamp and only observed values: `pi.online`, CPU/memory percentage, Pi thermal value when available (otherwise `null`), free disk MB, optional camera reachability, and MAVLink heartbeat age/system/component IDs. Bench acceptance is: propellers removed; power Pixhawk and Pi; verify TELEM2 heartbeat on Pi; verify health reaches the ground receiver; then temporarily remove/reconnect the ground link and confirm the companion continues monitoring and forwarding when restored. Hardware verification remains a bench task, not a flight task.

## Airborne / Recorded Audit Notes

- Uploads stream to bounded storage, validate readable video/image formats, use generated identifiers, and do not expose filesystem paths.
- Evidence and video serving resolve paths under their designated roots; traversal and symlink escape are rejected. Immutable originals are never overwritten.
- Mission mutations, captures, investigation, and analysis require admin access when authentication is enabled. Monitoring-route protection remains configurable for trusted LAN versus public deployment.
- MAVLink startup is disabled by default and rejects non-read-only configuration. It performs no outbound MAVLink operations.
- Recorded analysis has bounded concurrency, shares the sole YOLO instance, yields between samples, and does not invoke OCR or Web Intelligence automatically. Web search remains an explicit analyst action.
- Link availability and mission summaries derive from persisted packets/events; absent telemetry is represented as unavailable rather than estimated.

### Route security matrix

| Method | Route | `AUTH_ENABLED=false` | `AUTH_ENABLED=true`, `PROTECT_MONITORING_ROUTES=false` | `AUTH_ENABLED=true`, `PROTECT_MONITORING_ROUTES=true` | Mutates state |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | Public | Public | Public | No |
| GET | `/health`, `/ready` | Public | Public | Public | No |
| GET | `/status`, `/video`, `/alerts`, `/images`, `/outputs/*`, `/incidents`, `/zones`, `/rules/loitering` | Public | Public (trusted LAN) | Admin JWT/session | No |
| PUT/DELETE | `/zones`, `/zones/{id}` | Public | Admin JWT/session | Admin JWT/session | Yes |
| PUT | `/rules/loitering` | Public | Admin JWT/session | Admin JWT/session | Yes |
| POST | `/airborne/missions*` | Public | Admin JWT/session | Admin JWT/session | Yes |
| GET | `/airborne/missions*` | Public | Public (trusted LAN) | Admin JWT/session | No |

`PROTECT_MONITORING_ROUTES=false` is suitable only for local development or a trusted LAN protected by a firewall/VPN. Treat read-only routes as surveillance-sensitive. For public Internet deployments set it to `true`; browser-native MJPEG then needs a proper stream-auth design (the login's secure same-site session cookie, or a short-lived stream token), because an `<img>` cannot attach an Axios bearer interceptor.

## Testing

```powershell
python -m compileall -q backend
python -m pytest backend/tests -q
cd frontend
npm ci
npm run lint
npm run build
cd ..
docker compose config
```

## Troubleshooting

- Camera offline: inspect `/status`; check another program is not using the webcam, or verify RTSP access from the machine running FastAPI.
- Dashboard cannot connect: ensure `VITE_API_BASE_URL` points to the browser-visible backend address, then restart Vite.
- Docker on Windows: use RTSP. Run FastAPI locally for a physical Windows webcam.

## Security and limitations

Set `AUTH_ENABLED=true` with a strong `JWT_SECRET`, `ADMIN_USERNAME`, and bcrypt `ADMIN_PASSWORD_HASH` for trusted-LAN administration. Mutation endpoints for zones and loitering rules require an admin bearer token when enabled; surveillance viewing remains available to the LAN. Browser tokens use local storage, so deploy only over HTTPS and use a VPN/reverse proxy for access control. SQLite is suitable for a single-node deployment; use PostgreSQL only when multi-process/multi-node scale requires it. Camera hardware, RTSP credentials, model accuracy, and alert tuning require deployment-specific testing.

## Screenshots

Add dashboard and live-camera screenshots here for deployment documentation.
