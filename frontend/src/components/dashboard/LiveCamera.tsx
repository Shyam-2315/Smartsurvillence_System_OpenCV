import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Maximize2, Minimize2, Cpu, Activity, Radio } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fetchSystemStatus, videoStreamUrl } from "@/lib/api";

export function LiveCamera() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [streamLoaded, setStreamLoaded] = useState(false);
  const [streamFailed, setStreamFailed] = useState(false);
  const [streamAttempt, setStreamAttempt] = useState(0);
  const { data, error, isError } = useQuery({
    queryKey: ["system-status-camera"],
    queryFn: fetchSystemStatus,
    refetchInterval: 2000,
  });
  const cameraOnline = Boolean(data?.camera_online && streamLoaded);

  // Image elements do not reveal an MJPEG HTTP status. Retry after a camera
  // reconnect while /status remains authoritative for backend/camera state.
  useEffect(() => {
    if (!streamFailed) return;
    const id = window.setTimeout(() => {
      setStreamFailed(false);
      setStreamLoaded(false);
      setStreamAttempt((n) => n + 1);
    }, 5000);
    return () => window.clearTimeout(id);
  }, [streamFailed]);

  let streamMessage = "Waiting for first processed frame";
  let streamDetail = "The camera is connected; the AI worker has not produced a frame yet.";
  const statusCode = (error as { response?: { status?: number } } | null)?.response?.status;
  if (statusCode === 401 || statusCode === 403) {
    streamMessage = "Authentication/stream authorization error";
    streamDetail =
      "Sign in again, or allow trusted-LAN monitoring routes in the backend configuration.";
  } else if (isError) {
    streamMessage = "Backend unavailable";
    streamDetail = "Unable to read /status from the surveillance backend.";
  } else if (data && !data.camera_online) {
    streamMessage = "Camera source unavailable";
    streamDetail = "Check CAMERA_SOURCE and the camera reconnect status.";
  } else if (streamFailed) {
    streamMessage = "Stream unavailable/auth error";
    streamDetail =
      "If monitoring protection is enabled, browser-native MJPEG needs the login session cookie.";
  }

  const toggleFullscreen = async () => {
    if (!wrapRef.current) return;
    if (!document.fullscreenElement) {
      await wrapRef.current.requestFullscreen();
      setFullscreen(true);
    } else {
      await document.exitFullscreen();
      setFullscreen(false);
    }
  };
  const metric =
    typeof data?.ai_fps === "number"
      ? `${data.ai_fps.toFixed(1)} FPS`
      : typeof data?.last_inference_ms === "number"
        ? `${data.last_inference_ms.toFixed(0)} ms`
        : "Metrics pending";

  return (
    <motion.div
      ref={wrapRef}
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="glass scan-line relative overflow-hidden rounded-2xl"
    >
      <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-danger opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-danger" />
            </span>
            <span className="text-xs font-semibold uppercase tracking-widest">Live</span>
          </div>
          <Badge variant="outline" className="border-primary/40 text-primary">
            <Radio className="mr-1 h-3 w-3" /> CAM-01
          </Badge>
          <Badge
            variant="outline"
            className={
              cameraOnline ? "border-success/40 text-success" : "border-danger/40 text-danger"
            }
          >
            {cameraOnline ? "Online" : data?.camera_online ? "Waiting" : "Offline"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-primary/40 text-primary">
            <Cpu className="mr-1 h-3 w-3" /> {data?.using_cuda ? "GPU" : "CPU"}
          </Badge>
          <Badge variant="outline" className="border-primary/40 text-primary">
            <Activity className="mr-1 h-3 w-3" /> {metric}
          </Badge>
          <Button size="icon" variant="ghost" onClick={toggleFullscreen}>
            {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </Button>
        </div>
      </div>
      <div className="relative aspect-video w-full bg-black">
        <img
          key={streamAttempt}
          src={videoStreamUrl()}
          alt="Live feed"
          className="h-full w-full object-cover"
          onError={(event) => {
            setStreamLoaded(false);
            setStreamFailed(true);
            event.currentTarget.style.display = "none";
          }}
          onLoad={() => {
            setStreamLoaded(true);
            setStreamFailed(false);
          }}
        />
        {!cameraOnline && (
          <div className="absolute inset-0 grid-bg flex items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full border border-primary/40 bg-primary/10 pulse-ring">
                <Radio className="h-7 w-7 text-primary" />
              </div>
              <p className="text-sm font-medium">{streamMessage}</p>
              <p className="mt-1 text-xs text-muted-foreground">{streamDetail}</p>
            </div>
          </div>
        )}
        <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-md border border-primary/40 bg-background/40 px-2 py-1 backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full bg-primary pulse-ring" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-primary">
            {data?.ai_online ? "AI Detection Active" : "Camera feed active"}
          </span>
        </div>
        <div className="pointer-events-none absolute bottom-3 right-3 rounded-md border border-border/60 bg-background/60 px-2 py-1 text-[10px] uppercase tracking-widest backdrop-blur">
          {new Date().toLocaleTimeString()}
        </div>
      </div>
    </motion.div>
  );
}
