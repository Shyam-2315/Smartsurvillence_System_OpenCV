import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Maximize2, Minimize2, Cpu, Activity, Radio } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fetchSystemStatus, videoStreamUrl } from "@/lib/api";

export function LiveCamera() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [fps, setFps] = useState(28);
  const [fullscreen, setFullscreen] = useState(false);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const id = setInterval(() => setFps(24 + Math.floor(Math.random() * 10)), 1500);
    return () => clearInterval(id);
  }, []);

  const { data } = useQuery({
    queryKey: ["system-status-camera"],
    queryFn: fetchSystemStatus,
    refetchInterval: 2000,
  });

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
          <Badge variant="outline" className={online ? "border-success/40 text-success" : "border-danger/40 text-danger"}>
            {online ? "Online" : "Offline"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-primary/40 text-primary">
            <Cpu className="mr-1 h-3 w-3" /> {data?.using_cuda ? "GPU" : "CPU"}
          </Badge>
          <Badge variant="outline" className="border-primary/40 text-primary">
            <Activity className="mr-1 h-3 w-3" /> {data?.last_inference_ms ? `${Math.max(1, Math.round(1000 / data.last_inference_ms))}` : fps} FPS
          </Badge>
          <Button size="icon" variant="ghost" onClick={toggleFullscreen}>
            {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div className="relative aspect-video w-full bg-black">
        <img
          src={videoStreamUrl()}
          alt="Live feed"
          className="h-full w-full object-cover"
          onError={(e) => {
            setOnline(false);
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
          onLoad={() => setOnline(true)}
        />
        {!online && (
          <div className="absolute inset-0 grid-bg flex items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full border border-primary/40 bg-primary/10 pulse-ring">
                <Radio className="h-7 w-7 text-primary" />
              </div>
              <p className="text-sm font-medium">Awaiting stream from <code className="text-primary">/video</code></p>
              <p className="mt-1 text-xs text-muted-foreground">Start the FastAPI backend at 127.0.0.1:8001</p>
            </div>
          </div>
        )}
        <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-md border border-primary/40 bg-background/40 px-2 py-1 backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full bg-primary pulse-ring" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-primary">AI Detection Active</span>
        </div>
        <div className="pointer-events-none absolute bottom-3 right-3 rounded-md border border-border/60 bg-background/60 px-2 py-1 text-[10px] uppercase tracking-widest backdrop-blur">
          {new Date().toLocaleTimeString()}
        </div>
      </div>
    </motion.div>
  );
}
