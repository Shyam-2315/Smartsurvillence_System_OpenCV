import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ExternalLink, Loader2, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { MissionTrackMap } from "@/components/dashboard/MissionTrackMap";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  cancelRecordedAnalysis,
  extractRecordedMissionFrame,
  fetchMissionEvidence,
  fetchMissionEvents,
  fetchMissionReport,
  fetchRecordedAnalysisStatus,
  fetchRecordedMission,
  investigateMissionEvidence,
  missionEvidenceUrl,
  recordedMissionVideoUrl,
  startRecordedAnalysis,
  type MissionEvent,
} from "@/lib/api";

export const Route = createFileRoute("/recorded-missions/$missionId")({
  component: RecordedMissionDetailPage,
});

const formatTime = (seconds: number | undefined) => {
  const total = Math.max(0, Math.floor(seconds || 0));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
};

const eventData = (event: MissionEvent) => {
  const data = event.metadata;
  return {
    objectClass: typeof data.object_class === "string" ? data.object_class : "Object",
    confidence: typeof data.peak_confidence === "number" ? data.peak_confidence : undefined,
    timestamp: typeof data.start_seconds === "number" ? data.start_seconds : undefined,
  };
};

function RecordedMissionDetailPage() {
  const { missionId } = Route.useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const video = useRef<HTMLVideoElement>(null);
  const [currentTimestamp, setCurrentTimestamp] = useState(0);
  const mission = useQuery({
    queryKey: ["recorded-mission", missionId],
    queryFn: () => fetchRecordedMission(missionId),
  });
  const analysis = useQuery({
    queryKey: ["recorded-analysis", missionId],
    queryFn: () => fetchRecordedAnalysisStatus(missionId),
    refetchInterval: (query) => {
      const state = query.state.data?.status;
      return state === "QUEUED" || state === "PROCESSING" ? 2000 : false;
    },
  });
  const events = useQuery({
    queryKey: ["mission-events", missionId],
    queryFn: () => fetchMissionEvents(missionId),
    refetchInterval: analysis.data?.status === "PROCESSING" ? 3000 : false,
  });
  const evidence = useQuery({
    queryKey: ["mission-evidence", missionId],
    queryFn: () => fetchMissionEvidence(missionId),
    refetchInterval: analysis.data?.status === "PROCESSING" ? 3000 : false,
  });
  const report = useQuery({
    queryKey: ["mission-report", missionId],
    queryFn: () => fetchMissionReport(missionId),
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["recorded-mission", missionId] });
    queryClient.invalidateQueries({ queryKey: ["recorded-analysis", missionId] });
    queryClient.invalidateQueries({ queryKey: ["mission-events", missionId] });
    queryClient.invalidateQueries({ queryKey: ["mission-evidence", missionId] });
  };
  const start = useMutation({
    mutationFn: () => startRecordedAnalysis(missionId),
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: () => cancelRecordedAnalysis(missionId),
    onSuccess: refresh,
  });
  const captureFrame = useMutation({
    mutationFn: () => extractRecordedMissionFrame(missionId, currentTimestamp),
    onSuccess: refresh,
  });
  const investigate = useMutation({
    mutationFn: (evidenceId: string) => investigateMissionEvidence(missionId, evidenceId),
    onSuccess: (result) =>
      navigate({ to: "/visual-intelligence", search: { analysisId: result.id } }),
  });
  const detections = (events.data || []).filter(
    (event) => event.event_type === "recorded_detection",
  );
  const evidenceById = new Map((evidence.data || []).map((item) => [item.id, item]));

  if (mission.isLoading)
    return (
      <DashboardLayout title="Recorded Mission">
        <p className="text-muted-foreground">Loading mission…</p>
      </DashboardLayout>
    );
  if (mission.isError || !mission.data)
    return (
      <DashboardLayout title="Recorded Mission">
        <p className="text-destructive">Mission could not be loaded.</p>
      </DashboardLayout>
    );
  const item = mission.data;
  const job = analysis.data;
  const canCancel = job?.status === "QUEUED" || job?.status === "PROCESSING";

  function seek(seconds: number | undefined) {
    if (seconds == null || !video.current) return;
    video.current.currentTime = seconds;
    video.current.play().catch(() => undefined);
  }

  return (
    <DashboardLayout title="Recorded Mission">
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Link to="/recorded-missions" className="text-sm text-primary hover:underline">
              ← Recorded Missions
            </Link>
            <h1 className="mt-1 text-xl font-semibold">{item.name}</h1>
          </div>
          {!job && (
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Analyze Mission
            </Button>
          )}
          {canCancel && (
            <Button
              variant="destructive"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
            >
              <XCircle className="mr-2 h-4 w-4" />
              Cancel Analysis
            </Button>
          )}
        </div>
        <Card>
          <CardContent className="grid gap-3 p-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <p>
              Mission ID: <span className="font-mono text-xs">{item.id}</span>
            </p>
            <p>
              Duration: <strong>{formatTime(item.duration_seconds ?? undefined)}</strong>
            </p>
            <p>
              Source: <strong>{item.source_type}</strong>
            </p>
            <p>
              Processing:{" "}
              <Badge
                variant={
                  job?.status === "FAILED" || job?.status === "CANCELLED"
                    ? "destructive"
                    : "outline"
                }
              >
                {job?.status || item.processing_status || "ready"}
              </Badge>
            </p>
            <p>
              Created: <strong>{new Date(item.created_at).toLocaleString()}</strong>
            </p>
            <p>
              Resolution:{" "}
              <strong>
                {item.width} × {item.height} @ {item.fps} FPS
              </strong>
            </p>
          </CardContent>
        </Card>
        {job && (
          <Card>
            <CardContent className="space-y-2 p-4">
              <div className="flex justify-between text-sm">
                <span>{job.status}</span>
                <span>{Math.round(job.progress_percent)}%</span>
              </div>
              <Progress value={job.progress_percent} />
              <div className="flex gap-5 text-sm text-muted-foreground">
                <span>
                  {job.frames_processed} / {job.estimated_samples || "?"} frames processed
                </span>
                <span>{job.events_found} events found</span>
              </div>
              {job.error_message && <p className="text-sm text-destructive">{job.error_message}</p>}
            </CardContent>
          </Card>
        )}
        <Tabs defaultValue="overview">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="evidence">Evidence</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            {report.data && (
              <Card className="mb-4">
                <CardHeader>
                  <CardTitle>Mission summary</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
                  <p>
                    Duration:{" "}
                    <strong>
                      {formatTime(report.data.summary.mission_duration_seconds ?? undefined)}
                    </strong>
                  </p>
                  <p>
                    Events: <strong>{report.data.summary.events}</strong>
                  </p>
                  <p>
                    Detections: <strong>{report.data.summary.detections}</strong>
                  </p>
                  <p>
                    Evidence: <strong>{report.data.summary.evidence_count}</strong>
                  </p>
                  <p>
                    Visual analyses:{" "}
                    <strong>{report.data.summary.visual_intelligence_analyses}</strong>
                  </p>
                </CardContent>
              </Card>
            )}
            <Card>
              <CardHeader>
                <CardTitle>Mission video</CardTitle>
              </CardHeader>
              <CardContent>
                <video
                  ref={video}
                  className="max-h-[560px] w-full rounded bg-black"
                  controls
                  preload="metadata"
                  src={recordedMissionVideoUrl(missionId)}
                  onTimeUpdate={(event) => setCurrentTimestamp(event.currentTarget.currentTime)}
                >
                  Your browser does not support recorded mission playback.
                </video>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <Button onClick={() => captureFrame.mutate()} disabled={captureFrame.isPending}>
                    {captureFrame.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Capture Current Frame
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Current timestamp: {formatTime(currentTimestamp)}
                  </span>
                  {captureFrame.data && (
                    <Button
                      variant="outline"
                      onClick={() => investigate.mutate(captureFrame.data!.evidence.id)}
                      disabled={investigate.isPending}
                    >
                      Investigate
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
            {report.data && (
              <Card className="mt-4">
                <CardHeader>
                  <CardTitle>Mission map</CardTitle>
                </CardHeader>
                <CardContent>
                  <MissionTrackMap track={report.data.track} evidence={report.data.evidence} />
                </CardContent>
              </Card>
            )}
          </TabsContent>
          <TabsContent value="timeline">
            <Card>
              <CardHeader>
                <CardTitle>Detection timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {detections.map((event) => {
                  const data = eventData(event);
                  return (
                    <div
                      key={event.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded border p-3"
                    >
                      <button className="text-left" onClick={() => seek(data.timestamp)}>
                        <p className="font-medium">
                          {formatTime(data.timestamp)} · {data.objectClass} detected
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {data.confidence == null
                            ? "Confidence unavailable"
                            : `${Math.round(data.confidence * 100)}% confidence`}
                        </p>
                      </button>
                      {event.evidence_id && (
                        <div className="flex gap-2">
                          <a
                            href={missionEvidenceUrl(event.evidence_id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <Button variant="outline" size="sm">
                              View Evidence
                            </Button>
                          </a>
                          <Button
                            size="sm"
                            onClick={() => investigate.mutate(event.evidence_id!)}
                            disabled={investigate.isPending}
                          >
                            Investigate
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                })}
                {detections.length === 0 && (
                  <p className="text-sm text-muted-foreground">No recorded detection events yet.</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="evidence">
            <Card>
              <CardHeader>
                <CardTitle>Evidence gallery</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {detections
                  .filter((event) => event.evidence_id && evidenceById.has(event.evidence_id))
                  .map((event) => {
                    const data = eventData(event);
                    const id = event.evidence_id!;
                    return (
                      <article key={event.id} className="overflow-hidden rounded border">
                        <img
                          className="aspect-video w-full bg-muted object-cover"
                          src={missionEvidenceUrl(id)}
                          alt={`${data.objectClass} evidence`}
                        />
                        <div className="space-y-1 p-3 text-sm">
                          <p className="font-medium">{data.objectClass}</p>
                          <p className="text-muted-foreground">
                            {formatTime(data.timestamp)} ·{" "}
                            {data.confidence == null
                              ? "Confidence unavailable"
                              : `${Math.round(data.confidence * 100)}%`}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Event {event.id.slice(0, 8)}
                          </p>
                          <a href={missionEvidenceUrl(id)} target="_blank" rel="noreferrer">
                            <Button className="mt-2" variant="outline" size="sm">
                              Open Evidence
                              <ExternalLink className="ml-2 h-3 w-3" />
                            </Button>
                          </a>
                          <Button
                            className="mt-2"
                            onClick={() => investigate.mutate(id)}
                            disabled={investigate.isPending}
                          >
                            Investigate
                          </Button>
                        </div>
                      </article>
                    );
                  })}
                {evidence.data?.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Evidence is created for representative detection events.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
