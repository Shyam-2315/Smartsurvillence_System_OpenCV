import axios from "axios";
import { getToken } from "./token";

// Browser-facing URL only. Docker's internal `backend` hostname must never be used here.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(
  /\/$/,
  "",
);

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 8000,
  withCredentials: true,
});
api.interceptors.request.use((request) => {
  const token = getToken();
  if (token) request.headers.Authorization = `Bearer ${token}`;
  return request;
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
  configured_source?: string;
  last_frame_ts?: number | null;
  reconnect_attempts?: number;
  camera_connection_state?:
    | "CONNECTING"
    | "CONNECTED"
    | "DEGRADED"
    | "DISCONNECTED"
    | "RECONNECTING";
  camera_id?: string;
  camera_name?: string;
  camera_mode?: "fixed" | "airborne";
  tracking_notice?: string | null;
  telegram_enabled?: boolean;
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
    const { data } = await api.get<Incident[]>("incidents", { params: { limit: 50 } });
    if (!Array.isArray(data)) return [];
    return data.map((inc) => ({
      id: String(inc.id),
      type: (inc.type as AlertType) ?? "Loitering",
      severity: inc.severity ?? "medium",
      timestamp: new Date(inc.created_at_ts * 1000).toISOString(),
      message: inc.message ?? undefined,
      camera: inc.camera ?? undefined,
    }));
  } catch {
    return [];
  }
}

export async function fetchIncidents(params?: {
  limit?: number;
  offset?: number;
  type?: string;
  severity?: string;
  since_ts?: number;
}): Promise<Incident[]> {
  const { data } = await api.get<Incident[]>("incidents", { params });
  return data;
}

export async function fetchZones(): Promise<Zone[]> {
  const { data } = await api.get<Zone[]>("zones");
  return data;
}

export async function upsertZone(
  zone: Partial<Zone> & { name: string; points: [number, number][] },
): Promise<Zone> {
  const { data } = await api.put<Zone>("zones", zone);
  return data;
}

export async function deleteZone(zoneId: number): Promise<void> {
  await api.delete(`zones/${zoneId}`);
}

export async function fetchLoiterRule(): Promise<LoiterRule> {
  const { data } = await api.get<LoiterRule>("rules/loitering");
  return data;
}

export async function saveLoiterRule(rule: LoiterRule): Promise<LoiterRule> {
  const { data } = await api.put<LoiterRule>("rules/loitering", rule);
  return data;
}

export async function fetchImages(): Promise<CapturedImage[]> {
  try {
    const { data } = await api.get<CapturedImage[]>("images");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const { data } = await api.get<SystemStatus>("status");
  return data;
}
export interface AircraftTelemetry {
  timestamp: number;
  latitude: number | null;
  longitude: number | null;
  altitude_m: number | null;
  relative_altitude_m?: number | null;
  ground_speed_mps: number | null;
  air_speed_mps?: number | null;
  heading_deg: number | null;
  battery_percent: number | null;
  battery_voltage_v?: number | null;
  battery_current_a?: number | null;
  battery_remaining_percent?: number | null;
  system_id?: number | null;
  component_id?: number | null;
  gps_fix_type?: number | null;
  satellites_visible?: number | null;
  source?: "sitl" | "real" | "unknown";
  armed?: boolean | null;
  flight_mode?: string | null;
  gps_fix?: number | null;
  satellite_count?: number | null;
  roll_deg?: number | null;
  pitch_deg?: number | null;
  yaw_deg?: number | null;
  heartbeat_age_seconds?: number | null;
}
export async function fetchAircraftTelemetry(cameraId: string): Promise<AircraftTelemetry | null> {
  const { data } = await api.get<{ telemetry: AircraftTelemetry | null }>(
    `telemetry/aircraft/${cameraId}`,
  );
  return data.telemetry;
}
export async function captureCameraFrame(
  cameraId: string,
): Promise<{ incident: Incident; filename: string; sha256: string }> {
  const { data } = await api.post(`cameras/${cameraId}/capture`);
  return data;
}

export interface AirborneStatus {
  state: "DISABLED" | "CONNECTING" | "CONNECTED" | "STALE" | "DISCONNECTED" | "RECONNECTING";
  connection: string | null;
  read_only: boolean;
  heartbeat_age_seconds: number | null;
  camera_id: string;
  camera_name: string;
  simulation: boolean;
  telemetry_source: "sitl" | "real" | "unknown";
}

export interface AirborneTelemetryLatest {
  camera_id: string;
  telemetry: AircraftTelemetry | null;
  mavlink: AirborneStatus;
}

export async function fetchAirborneStatus(): Promise<AirborneStatus> {
  const { data } = await api.get<AirborneStatus>("airborne/status");
  return data;
}

export async function fetchAirborneTelemetry(): Promise<AirborneTelemetryLatest> {
  const { data } = await api.get<AirborneTelemetryLatest>("airborne/telemetry/latest");
  return data;
}

export function imageUrl(filename: string) {
  return `${API_BASE}/outputs/${filename}`;
}

export function videoStreamUrl() {
  return `${API_BASE}/video`;
}

export type RecordedAnalysisState = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface RecordedMission {
  id: string;
  name: string;
  source_type: "live" | "recorded";
  camera_id: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  status: "planned" | "active" | "completed" | "aborted";
  notes: string | null;
  original_video_sha256: string | null;
  duration_seconds: number | null;
  fps: number | null;
  width: number | null;
  height: number | null;
  frame_count: number | null;
  processing_status: RecordedAnalysisState | "ready" | null;
}

export interface RecordedAnalysisJob {
  id: string;
  mission_id: string;
  status: RecordedAnalysisState;
  progress_percent: number;
  frames_processed: number;
  estimated_samples: number;
  events_found: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
}

export interface MissionEvent {
  id: string;
  mission_id: string;
  timestamp: string;
  event_type: string;
  severity: string;
  camera_id: string | null;
  incident_id: number | null;
  evidence_id: string | null;
  analysis_id: string | null;
  metadata: Record<string, unknown>;
}

export interface MissionEvidence {
  id: string;
  mission_id: string | null;
  created_at: string;
  capture_timestamp: string;
  source_type: string;
  sha256: string;
  analysis_id: string | null;
  latitude?: number | null;
  longitude?: number | null;
  altitude_m?: number | null;
  heading_deg?: number | null;
  original_available: boolean;
}

export interface ExtractedMissionFrame {
  evidence: MissionEvidence;
  event: MissionEvent;
}

export async function fetchRecordedMissions(): Promise<RecordedMission[]> {
  const { data } = await api.get<RecordedMission[]>("airborne/missions", {
    params: { limit: 100 },
  });
  return data.filter((mission) => mission.source_type === "recorded");
}

export async function fetchLiveMissions(): Promise<RecordedMission[]> {
  const { data } = await api.get<RecordedMission[]>("airborne/missions", {
    params: { limit: 100 },
  });
  return data.filter((mission) => mission.source_type === "live");
}

export async function createLiveMission(cameraId: string): Promise<RecordedMission> {
  const { data } = await api.post<RecordedMission>("airborne/missions", {
    name: `Live airborne mission ${new Date().toLocaleString()}`,
    source_type: "live",
    camera_id: cameraId,
  });
  return data;
}

export async function transitionLiveMission(
  missionId: string,
  action: "start" | "complete" | "abort",
): Promise<RecordedMission> {
  const { data } = await api.post<RecordedMission>(`airborne/missions/${missionId}/${action}`);
  return data;
}

export interface LiveAirborneCapture {
  evidence: MissionEvidence;
  event: MissionEvent | null;
  telemetry_association: {
    telemetry: AircraftTelemetry;
    telemetry_timestamp: number;
    delta_ms: number;
  } | null;
}

export async function captureLiveAirborneFrame(): Promise<LiveAirborneCapture> {
  const { data } = await api.post<LiveAirborneCapture>("airborne/live/capture");
  return data;
}

export async function investigateLiveAirborneEvidence(evidenceId: string): Promise<VisualAnalysis> {
  const { data } = await api.post<VisualAnalysis>(`airborne/evidence/${evidenceId}/investigate`);
  return data;
}

export async function fetchRecordedMission(id: string): Promise<RecordedMission> {
  const { data } = await api.get<RecordedMission>(`airborne/missions/recorded/${id}`);
  return data;
}

export async function uploadRecordedMission(
  name: string,
  video: File,
  notes?: string,
): Promise<RecordedMission> {
  const body = new FormData();
  body.append("name", name);
  body.append("video", video);
  if (notes?.trim()) body.append("notes", notes.trim());
  const { data } = await api.post<RecordedMission>("airborne/missions/recorded", body);
  return data;
}

export async function startRecordedAnalysis(id: string): Promise<RecordedAnalysisJob> {
  const { data } = await api.post<RecordedAnalysisJob>(`airborne/missions/recorded/${id}/analyze`);
  return data;
}

export async function fetchRecordedAnalysisStatus(id: string): Promise<RecordedAnalysisJob | null> {
  try {
    const { data } = await api.get<RecordedAnalysisJob>(
      `airborne/missions/recorded/${id}/analysis-status`,
    );
    return data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null;
    throw error;
  }
}

export async function cancelRecordedAnalysis(id: string): Promise<RecordedAnalysisJob> {
  const { data } = await api.post<RecordedAnalysisJob>(`airborne/missions/recorded/${id}/cancel`);
  return data;
}

export async function fetchMissionEvents(id: string): Promise<MissionEvent[]> {
  const { data } = await api.get<MissionEvent[]>(`airborne/missions/${id}/events`);
  return data;
}

export async function fetchMissionEvidence(id: string): Promise<MissionEvidence[]> {
  const { data } = await api.get<MissionEvidence[]>(`airborne/missions/${id}/evidence`);
  return data;
}

export interface MissionSummary {
  mission_id: string;
  mission_duration_seconds: number | null;
  events: number;
  detections: number;
  evidence_count: number;
  visual_intelligence_analyses: number;
  video_availability_percent?: number | null;
  telemetry_availability_percent?: number | null;
  disconnect_count?: number;
  longest_outage_seconds?: number;
}

export interface MissionTrackPoint {
  timestamp: number;
  latitude: number;
  longitude: number;
  altitude_m: number | null;
}

export interface MissionReport {
  report_version: string;
  mission: RecordedMission;
  summary: MissionSummary;
  track: MissionTrackPoint[];
  events: MissionEvent[];
  evidence: MissionEvidence[];
  analyses: {
    id: string;
    created_at: string;
    source_type: string;
    status: string;
    mission_event_id: string | null;
    evidence_id: string | null;
    video_timestamp_seconds: number | null;
  }[];
}

export async function fetchMissionReport(id: string): Promise<MissionReport> {
  const { data } = await api.get<MissionReport>(`airborne/missions/${id}/report`);
  return data;
}

export async function extractRecordedMissionFrame(
  missionId: string,
  timestampSeconds: number,
): Promise<ExtractedMissionFrame> {
  const { data } = await api.post<ExtractedMissionFrame>(
    `airborne/missions/${missionId}/extract-frame`,
    {
      timestamp_seconds: timestampSeconds,
    },
  );
  return data;
}

export async function investigateMissionEvidence(
  missionId: string,
  evidenceId: string,
): Promise<VisualAnalysis> {
  const { data } = await api.post<VisualAnalysis>(
    `airborne/missions/${missionId}/evidence/${evidenceId}/investigate`,
  );
  return data;
}

export function recordedMissionVideoUrl(id: string) {
  return `${API_BASE}/airborne/missions/${id}/video`;
}

export function missionEvidenceUrl(id: string) {
  return `${API_BASE}/airborne/evidence/${id}/original`;
}

export interface VisualAnalysis {
  id: string;
  created_at: string;
  original_filename: string;
  stored_original_path: string;
  sha256: string;
  width: number;
  height: number;
  status: string;
  source_type: string;
  mission_id?: string | null;
  mission_event_id?: string | null;
  evidence_id?: string | null;
  video_timestamp_seconds?: number | null;
  ocr: { text: string; confidence: number; box: number[][] }[];
  detections: { class: string; confidence: number; bbox: number[] }[];
  entities: Record<string, string[]>;
  search_queries: { query: string; score: number; evidence: string[] }[];
  web_results: {
    title: string;
    url: string;
    snippet: string;
    domain: string;
    source_type?: string;
  }[];
  summary: {
    assessment?: { summary?: string; confidence?: string; limitations?: string[] };
    web_intelligence?: { notice?: string; status?: { status?: string; reason?: string } };
    correlation?: {
      inferred?: {
        candidate_matches?: { name: string; confidence: string; supporting_evidence: string[] }[];
        contradictions?: string[];
      };
    };
  };
  metadata: {
    derivatives?: Record<string, string>;
    evidence_notice?: string;
    ocr_notice?: string;
    ocr_status?: { state?: string; message?: string };
    region_normalized?: unknown;
  };
}
export async function uploadVisualImage(file: File): Promise<VisualAnalysis> {
  const body = new FormData();
  body.append("image", file);
  const { data } = await api.post<VisualAnalysis>("visual-intelligence/analyze", body);
  return data;
}
export async function fetchVisualAnalysis(id: string): Promise<VisualAnalysis> {
  const { data } = await api.get(`visual-intelligence/analyses/${id}`);
  return data;
}
export async function enhanceVisual(
  id: string,
  params: Record<string, unknown>,
): Promise<VisualAnalysis> {
  const { data } = await api.post(`visual-intelligence/analyses/${id}/enhance`, params);
  return data;
}
export async function regionVisual(
  id: string,
  region: { x: number; y: number; width: number; height: number },
): Promise<VisualAnalysis> {
  const { data } = await api.post(`visual-intelligence/analyses/${id}/regions/analyze`, region);
  return data;
}
export async function searchVisual(id: string, selected_text?: string): Promise<VisualAnalysis> {
  const { data } = await api.post(`visual-intelligence/analyses/${id}/web-search`, {
    selected_text: selected_text || null,
  });
  return data;
}
export function visualFileUrl(path: string) {
  return `${API_BASE}/visual-intelligence/files/${path}`;
}
