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
  ai_fps?: number | null;
  gpu_mem_mb?: number | null;
  last_updated_ts: number | null;
}

export interface Incident {
  id: number;
  created_at_ts: number;
  type: string;
  severity: AlertSeverity;
  message?: string | null;
  camera?: string | null;
  zone_id?: number | null;
  track_id?: number | null;
  duration_sec?: number | null;
  screenshot_filename?: string | null;
}

export interface Zone {
  id: number;
  name: string;
  points: [number, number][];
}

export interface LoiterRule {
  enabled: boolean;
  min_duration_sec: number;
  zone_id: number | null;
  cooldown_sec: number;
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
    const { data } = await api.get<Incident[]>("/incidents", { params: { limit: 50 } });
    if (!Array.isArray(data) || !data.length) return mockAlerts();
    return data.map((inc) => ({
      id: String(inc.id),
      type: (inc.type as AlertType) ?? "Loitering",
      severity: inc.severity ?? "medium",
      timestamp: new Date(inc.created_at_ts * 1000).toISOString(),
      message: inc.message ?? undefined,
      camera: inc.camera ?? undefined,
    }));
  } catch {
    return mockAlerts();
  }
}

export async function fetchIncidents(params?: { limit?: number; offset?: number; type?: string; severity?: string; since_ts?: number }): Promise<Incident[]> {
  const { data } = await api.get<Incident[]>("/incidents", { params });
  return data;
}

export async function fetchZones(): Promise<Zone[]> {
  const { data } = await api.get<Zone[]>("/zones");
  return data;
}

export async function upsertZone(zone: Partial<Zone> & { name: string; points: [number, number][] }): Promise<Zone> {
  const { data } = await api.put<Zone>("/zones", zone);
  return data;
}

export async function deleteZone(zoneId: number): Promise<void> {
  await api.delete(`/zones/${zoneId}`);
}

export async function fetchLoiterRule(): Promise<LoiterRule> {
  const { data } = await api.get<LoiterRule>("/rules/loitering");
  return data;
}

export async function saveLoiterRule(rule: LoiterRule): Promise<LoiterRule> {
  const { data } = await api.put<LoiterRule>("/rules/loitering", rule);
  return data;
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
