import axios from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 8000,
});

export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type AlertType =
  | "Intrusion"
  | "Loitering"
  | "Running Detection"
  | "Crowd Detection"
  | "Unauthorized Access";

export interface Alert {
  id: string;
  type: AlertType;
  timestamp: string;
  severity: AlertSeverity;
  message?: string;
  camera?: string;
}

export interface CapturedImage {
  filename: string;
  timestamp: string;
  type?: string;
}

interface BackendAlert {
  track_id: number;
  duration_sec: number;
}

interface BackendAlertEvent {
  track_id: number;
  duration_sec: number;
  screenshot_path?: string;
  message?: string;
  timestamp: number;
}

interface AlertsResponse {
  active_alerts: BackendAlert[];
  history: BackendAlertEvent[];
}

export interface SystemStatus {
  camera_online: boolean;
  ai_online: boolean;
  using_cuda: boolean;
  detections: number;
  tracks: number;
  active_alerts: number;
  last_inference_ms: number | null;
  last_updated_ts: number | null;
}

const ALERT_TYPES: AlertType[] = [
  "Intrusion",
  "Loitering",
  "Running Detection",
  "Crowd Detection",
  "Unauthorized Access",
];
const SEVERITIES: AlertSeverity[] = ["low", "medium", "high", "critical"];

function mockAlerts(count = 12): Alert[] {
  const now = Date.now();
  return Array.from({ length: count }).map((_, i) => ({
    id: `mock-${now}-${i}`,
    type: ALERT_TYPES[Math.floor(Math.random() * ALERT_TYPES.length)],
    severity: SEVERITIES[Math.floor(Math.random() * SEVERITIES.length)],
    timestamp: new Date(now - i * 1000 * 60 * (Math.random() * 8 + 1)).toISOString(),
    message: "AI detected anomalous behavior in monitored zone.",
    camera: `CAM-${String(Math.floor(Math.random() * 8) + 1).padStart(2, "0")}`,
  }));
}

function mockImages(count = 18): CapturedImage[] {
  const now = Date.now();
  return Array.from({ length: count }).map((_, i) => ({
    filename: `capture_${i + 1}.jpg`,
    timestamp: new Date(now - i * 1000 * 60 * 7).toISOString(),
    type: ALERT_TYPES[i % ALERT_TYPES.length],
  }));
}

export async function fetchAlerts(): Promise<Alert[]> {
  try {
    const { data } = await api.get<AlertsResponse>("/alerts");
    if (!data || !Array.isArray(data.history)) return mockAlerts();
    return data.history.map((item, i) => ({
      id: `${item.track_id}-${item.timestamp}-${i}`,
      type: "Loitering",
      severity: item.duration_sec >= 30 ? "critical" : item.duration_sec >= 20 ? "high" : "medium",
      timestamp: new Date(item.timestamp * 1000).toISOString(),
      message: item.message || `Loitering detected for ${item.duration_sec}s`,
      camera: "CAM-01",
    }));
  } catch {
    return mockAlerts();
  }
}

export async function fetchImages(): Promise<CapturedImage[]> {
  try {
    const { data } = await api.get<CapturedImage[]>("/images");
    if (Array.isArray(data) && data.length) return data;
    return mockImages();
  } catch {
    return mockImages();
  }
}

export async function fetchSystemStatus(): Promise<SystemStatus | null> {
  try {
    const { data } = await api.get<SystemStatus>("/status");
    return data;
  } catch {
    return null;
  }
}

export function imageUrl(filename: string) {
  return `${API_BASE}/outputs/${filename}`;
}

export function videoStreamUrl() {
  return `${API_BASE}/video`;
}
