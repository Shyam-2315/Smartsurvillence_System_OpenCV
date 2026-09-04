import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { Cpu, Eye, ShieldAlert } from "lucide-react";
import { fetchSystemStatus } from "@/lib/api";

export function AIStatusBar() {
  const { data, isError } = useQuery({
    queryKey: ["system-status"],
    queryFn: fetchSystemStatus,
    refetchInterval: 2000,
  });

  const objects = data?.tracks ?? 0;
  const threat =
    (data?.active_alerts ?? 0) > 0
      ? "ELEVATED"
      : data?.camera_online && data?.ai_online
        ? "LOW"
        : "UNKNOWN";
  const fps =
    data?.ai_fps ??
    (data?.last_inference_ms ? Math.max(1, Math.round(1000 / data.last_inference_ms)) : null);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass flex flex-wrap items-center justify-between gap-3 rounded-2xl px-4 py-2.5"
    >
      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
          </span>
          <span className="font-semibold uppercase tracking-widest text-primary">
            {isError
              ? "Backend Offline"
              : data?.ai_online
                ? "AI Detection Active"
                : "AI Engine Waiting"}
          </span>
        </span>
        <span className="hidden items-center gap-1 text-muted-foreground sm:inline-flex">
          <Cpu className="h-3.5 w-3.5" />{" "}
          {data?.using_cuda ? "GPU Acceleration • CUDA" : "CPU Inference"}
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Eye className="h-3.5 w-3.5 text-primary" /> Objects:{" "}
          <span className="font-semibold text-foreground">{objects}</span>
        </span>
        <span className={data?.camera_online ? "text-success" : "text-danger"}>
          Camera: {data?.camera_online ? "Online" : "Offline"}
        </span>
        <span className={data?.telegram_enabled ? "text-success" : "text-muted-foreground"}>
          Telegram: {data?.telegram_enabled ? "Enabled" : "Disabled"}
        </span>
        <span className="flex items-center gap-1.5">
          <ShieldAlert className="h-3.5 w-3.5 text-warning" />
          <span className="text-muted-foreground">Threat:</span>
          <span className="rounded-md border border-warning/40 bg-warning/10 px-1.5 py-0.5 text-warning">
            {threat}
          </span>
        </span>
        {fps !== null && (
          <span className="hidden items-center gap-1.5 text-muted-foreground md:inline-flex">
            <span className="text-muted-foreground">FPS:</span>{" "}
            <span className="font-semibold text-foreground">{fps}</span>
          </span>
        )}
        {typeof data?.gpu_mem_mb === "number" && (
          <span className="hidden items-center gap-1.5 text-muted-foreground lg:inline-flex">
            <span className="text-muted-foreground">VRAM:</span>{" "}
            <span className="font-semibold text-foreground">{data.gpu_mem_mb} MB</span>
          </span>
        )}
      </div>
    </motion.div>
  );
}
