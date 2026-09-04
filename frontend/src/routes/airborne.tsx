import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Camera, CircleDot, Plane, Radio, Sparkles } from "lucide-react";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  captureLiveAirborneFrame,
  createLiveMission,
  fetchAirborneStatus,
  fetchAirborneTelemetry,
  fetchLiveMissions,
  fetchSystemStatus,
  investigateLiveAirborneEvidence,
  transitionLiveMission,
  videoStreamUrl,
} from "@/lib/api";

export const Route = createFileRoute("/airborne")({ component: AirbornePage });
const value = (item: unknown, suffix = "") =>
  item === null || item === undefined || item === "" ? "--" : `${item}${suffix}`;

function AirbornePage() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const system = useQuery({
    queryKey: ["status"],
    queryFn: fetchSystemStatus,
    refetchInterval: 2000,
  });
  const airborne = useQuery({
    queryKey: ["airborne-status"],
    queryFn: fetchAirborneStatus,
    refetchInterval: 2000,
  });
  const telemetry = useQuery({
    queryKey: ["airborne-telemetry"],
    queryFn: fetchAirborneTelemetry,
    refetchInterval: 1000,
  });
  const missions = useQuery({
    queryKey: ["live-missions"],
    queryFn: fetchLiveMissions,
    refetchInterval: 3000,
  });
  const active = missions.data?.find((mission) => mission.status === "active");
  const refresh = () => client.invalidateQueries({ queryKey: ["live-missions"] });
  const start = useMutation({
    mutationFn: async () =>
      transitionLiveMission(
        (await createLiveMission(telemetry.data?.camera_id || "AIR-01")).id,
        "start",
      ),
    onSuccess: refresh,
  });
  const complete = useMutation({
    mutationFn: () => transitionLiveMission(active!.id, "complete"),
    onSuccess: refresh,
  });
  const abort = useMutation({
    mutationFn: () => transitionLiveMission(active!.id, "abort"),
    onSuccess: refresh,
  });
  const capture = useMutation({ mutationFn: captureLiveAirborneFrame });
  const investigate = useMutation({
    mutationFn: (id: string) => investigateLiveAirborneEvidence(id),
    onSuccess: (analysis) =>
      navigate({ to: "/visual-intelligence", search: { analysisId: analysis.id } }),
  });
  const t = telemetry.data?.telemetry;
  const frameAge = system.data?.last_frame_ts
    ? Math.max(0, Date.now() / 1000 - system.data.last_frame_ts)
    : null;
  const video =
    system.data?.camera_connection_state ||
    (system.data?.camera_online
      ? "CONNECTED"
      : frameAge !== null && frameAge < 5
        ? "DEGRADED"
        : "DISCONNECTED");
  const metrics: [string, string][] = [
    ["Latitude", value(t?.latitude)],
    ["Longitude", value(t?.longitude)],
    ["Altitude", value(t?.altitude_m, " m")],
    ["Speed", value(t?.ground_speed_mps, " m/s")],
    ["Heading", value(t?.heading_deg, "°")],
    ["Battery", value(t?.battery_remaining_percent ?? t?.battery_percent, "%")],
    ["Flight Mode", value(t?.flight_mode)],
    ["GPS Fix", value(t?.gps_fix_type ?? t?.gps_fix)],
    ["Satellites", value(t?.satellites_visible ?? t?.satellite_count)],
    ["Armed", t?.armed == null ? "--" : t.armed ? "Armed" : "Disarmed"],
  ];
  return (
    <DashboardLayout title="Airborne Command Center">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Plane className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-xl font-semibold">
                {airborne.data?.camera_id || telemetry.data?.camera_id || "AIR-01"}
              </h1>
              <p className="text-sm text-muted-foreground">
                {airborne.data?.camera_name || "VAYU-X"} · {system.data?.configured_source || "--"}
              </p>
            </div>
          </div>
          <Badge variant={active ? "default" : "outline"}>
            {active ? `Active: ${active.name}` : "No active mission"}
          </Badge>
          {airborne.data?.simulation && <Badge variant="secondary">SIMULATION</Badge>}
        </div>
        <Card>
          <CardContent className="grid gap-3 p-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <p>
              Video: <strong>{video}</strong>
            </p>
            <p>
              Telemetry: <strong>{airborne.data?.state || "DISABLED"}</strong>
            </p>
            <p>
              Aircraft:{" "}
              <strong>
                {airborne.data?.telemetry_source === "sitl"
                  ? "SITL"
                  : airborne.data?.telemetry_source === "real"
                    ? "PIXHAWK"
                    : "--"}
              </strong>
            </p>
            <p>
              Simulation: <strong>{airborne.data?.simulation ? "YES" : "NO"}</strong>
            </p>
            <p>
              System ID: <strong>{value(t?.system_id)}</strong> · Component ID:{" "}
              <strong>{value(t?.component_id)}</strong>
            </p>
            <p>
              AI: <strong>{system.data?.ai_online ? "Running" : "--"}</strong>
            </p>
            <p>
              FPS: <strong>{value(system.data?.ai_fps)}</strong>
            </p>
            <p>
              Telemetry age: <strong>{value(airborne.data?.heartbeat_age_seconds, " s")}</strong>
            </p>
            <p>
              Frame age:{" "}
              <strong>{value(frameAge === null ? null : frameAge.toFixed(1), " s")}</strong>
            </p>
            <p>
              Reconnects: <strong>{value(system.data?.reconnect_attempts)}</strong>
            </p>
            <p>
              Source mode: <strong>{system.data?.camera_mode || "--"}</strong>
            </p>
          </CardContent>
        </Card>
        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Radio className="h-5 w-5" />
                Live video
              </CardTitle>
            </CardHeader>
            <CardContent>
              <img
                src={videoStreamUrl()}
                className="aspect-video w-full rounded bg-black object-contain"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={() => capture.mutate()} disabled={capture.isPending}>
                  <Camera className="mr-2 h-4 w-4" />
                  Capture Frame
                </Button>
                {capture.data && (
                  <Button
                    variant="outline"
                    onClick={() => investigate.mutate(capture.data!.evidence.id)}
                    disabled={investigate.isPending}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    Investigate
                  </Button>
                )}
              </div>
              {capture.data && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Immutable evidence · telemetry{" "}
                  {capture.data.telemetry_association
                    ? `matched (${capture.data.telemetry_association.delta_ms} ms)`
                    : "unavailable"}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CircleDot className="h-5 w-5" />
                Mission
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {active ? (
                <>
                  <p className="font-medium">{active.name}</p>
                  <p className="text-muted-foreground">
                    Started{" "}
                    {active.started_at ? new Date(active.started_at).toLocaleString() : "--"}
                  </p>
                  <div className="flex gap-2">
                    <Button onClick={() => complete.mutate()} disabled={complete.isPending}>
                      Complete Mission
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => abort.mutate()}
                      disabled={abort.isPending}
                    >
                      Abort Mission
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <p className="text-muted-foreground">
                    Start a mission before flight evidence and telemetry are associated.
                  </p>
                  <Button onClick={() => start.mutate()} disabled={start.isPending}>
                    Start Mission
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
        <section>
          <h2 className="mb-3 text-lg font-semibold">Telemetry</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {metrics.map(([label, item]) => (
              <Card key={label}>
                <CardContent className="p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
                  <p className="mt-1 font-semibold">{item}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}
