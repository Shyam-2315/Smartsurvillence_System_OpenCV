import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Loader2, Upload } from "lucide-react";
import { FormEvent, useState } from "react";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  fetchMissionEvidence,
  fetchMissionEvents,
  fetchRecordedMissions,
  missionEvidenceUrl,
  recordedMissionVideoUrl,
  startRecordedAnalysis,
  type RecordedMission,
  uploadRecordedMission,
} from "@/lib/api";

export const Route = createFileRoute("/recorded-missions")({ component: RecordedMissionsPage });

const duration = (seconds: number | null) => {
  if (seconds == null) return "Unavailable";
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
};

function statusVariant(status: string | null) {
  if (status === "FAILED" || status === "CANCELLED") return "destructive" as const;
  return status === "COMPLETED" ? ("secondary" as const) : ("outline" as const);
}

function RecordedMissionsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [video, setVideo] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [uploaded, setUploaded] = useState<RecordedMission | null>(null);
  const [error, setError] = useState("");
  const missions = useQuery({
    queryKey: ["recorded-missions"],
    queryFn: async () => {
      const records = await fetchRecordedMissions();
      return Promise.all(
        records.map(async (mission) => {
          const [events, evidence] = await Promise.all([
            fetchMissionEvents(mission.id),
            fetchMissionEvidence(mission.id),
          ]);
          return {
            mission,
            eventCount: events.filter((event) => event.event_type === "recorded_detection").length,
            evidenceCount: evidence.length,
            thumbnailEvidenceId: evidence.find((item) => item.original_available)?.id,
          };
        }),
      );
    },
  });
  const upload = useMutation({
    mutationFn: () => uploadRecordedMission(name.trim(), video!, notes),
    onSuccess: (mission) => {
      setUploaded(mission);
      setName("");
      setVideo(null);
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["recorded-missions"] });
    },
    onError: () =>
      setError("Upload failed. Confirm the video format and your access, then try again."),
  });
  const analyze = useMutation({
    mutationFn: (id: string) => startRecordedAnalysis(id),
    onSuccess: (_job, id) =>
      navigate({ to: "/recorded-missions/$missionId", params: { missionId: id } }),
    onError: () => setError("Analysis could not be started."),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!name.trim() || !video) {
      setError("Mission name and a video file are required.");
      return;
    }
    upload.mutate();
  }

  return (
    <DashboardLayout title="Recorded Missions">
      <div className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Upload Mission Video
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4 md:grid-cols-2" onSubmit={submit}>
              <label className="grid gap-1 text-sm font-medium">
                Mission Name
                <Input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={200}
                />
              </label>
              <label className="grid gap-1 text-sm font-medium">
                Video
                <Input
                  type="file"
                  accept="video/*"
                  onChange={(event) => setVideo(event.target.files?.[0] || null)}
                />
              </label>
              <label className="grid gap-1 text-sm font-medium md:col-span-2">
                Notes (optional)
                <Textarea
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  maxLength={4000}
                />
              </label>
              <div className="flex items-center gap-3 md:col-span-2">
                <Button type="submit" disabled={upload.isPending}>
                  {upload.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Upload
                  Mission Video
                </Button>
                {error && <p className="text-sm text-destructive">{error}</p>}
              </div>
            </form>
            {uploaded && (
              <div className="mt-5 rounded-md border border-primary/30 bg-primary/5 p-4 text-sm">
                <p className="font-semibold">{uploaded.name} uploaded</p>
                <div className="mt-2 grid gap-1 sm:grid-cols-2">
                  <span>Duration: {duration(uploaded.duration_seconds)}</span>
                  <span>
                    Resolution: {uploaded.width} × {uploaded.height}
                  </span>
                  <span>FPS: {uploaded.fps ?? "Unavailable"}</span>
                  <span>
                    SHA-256: {uploaded.original_video_sha256?.slice(0, 12) ?? "Unavailable"}…
                  </span>
                </div>
                <Button
                  className="mt-3"
                  onClick={() => analyze.mutate(uploaded.id)}
                  disabled={analyze.isPending}
                >
                  Analyze Mission
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
        <section>
          <h2 className="mb-3 text-lg font-semibold">Recent missions</h2>
          {missions.isLoading ? (
            <p className="text-muted-foreground">Loading missions…</p>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {missions.data?.map(({ mission, eventCount, evidenceCount, thumbnailEvidenceId }) => (
                <Link
                  key={mission.id}
                  to="/recorded-missions/$missionId"
                  params={{ missionId: mission.id }}
                  className="block"
                >
                  <Card className="overflow-hidden transition-colors hover:border-primary/60">
                    <CardContent className="flex gap-3 p-3">
                      {thumbnailEvidenceId ? (
                        <img
                          className="h-24 w-36 rounded bg-black object-cover"
                          src={missionEvidenceUrl(thumbnailEvidenceId)}
                          alt={`${mission.name} evidence thumbnail`}
                        />
                      ) : (
                        <video
                          className="h-24 w-36 rounded bg-black object-cover"
                          muted
                          preload="metadata"
                          src={recordedMissionVideoUrl(mission.id)}
                        />
                      )}
                      <div className="min-w-0 space-y-1 text-sm">
                        <p className="truncate font-semibold">{mission.name}</p>
                        <p className="text-muted-foreground">
                          {duration(mission.duration_seconds)} ·{" "}
                          {new Date(mission.created_at).toLocaleString()}
                        </p>
                        <Badge variant={statusVariant(mission.processing_status)}>
                          {mission.processing_status || "ready"}
                        </Badge>
                        <p className="text-muted-foreground">
                          {eventCount} events · {evidenceCount} evidence items
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
              {missions.data?.length === 0 && (
                <Card>
                  <CardContent className="p-6 text-sm text-muted-foreground">
                    No recorded missions yet.
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}
