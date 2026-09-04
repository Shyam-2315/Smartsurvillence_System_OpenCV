import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ShieldAlert, Footprints, Users, Zap, Lock } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import { Alert, AlertType, fetchAlerts } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const iconMap: Record<AlertType, typeof AlertTriangle> = {
  Intrusion: ShieldAlert,
  Loitering: Footprints,
  "Running Detection": Zap,
  "Crowd Detection": Users,
  "Unauthorized Access": Lock,
};

const severityStyles: Record<string, string> = {
  low: "border-success/40 bg-success/10 text-success",
  medium: "border-warning/40 bg-warning/10 text-warning",
  high: "border-danger/40 bg-danger/10 text-danger",
  critical: "border-danger/60 bg-danger/20 text-danger",
};

export function AlertsPanel({ limit }: { limit?: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["alerts"],
    queryFn: fetchAlerts,
    refetchInterval: 3000,
  });
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!data) return;
    const fresh = data.filter((a) => !seen.current.has(a.id));
    if (seen.current.size > 0) {
      fresh.slice(0, 2).forEach((a) =>
        toast(a.type, {
          description: `${a.camera ?? "Camera"} • ${a.severity.toUpperCase()}`,
          icon: <AlertTriangle className="h-4 w-4 text-warning" />,
        }),
      );
    }
    data.forEach((a) => seen.current.add(a.id));
  }, [data]);

  const items = (data ?? []).slice(0, limit ?? 50);

  return (
    <div className="glass flex h-full flex-col rounded-2xl">
      <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-widest">Live Alerts</h3>
          <p className="text-xs text-muted-foreground">Auto-refresh every 3s</p>
        </div>
        <span className="flex items-center gap-1.5 text-xs text-success">
          <span className="h-2 w-2 rounded-full bg-success pulse-ring" /> Streaming
        </span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {isLoading &&
          Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        {isError && (
          <p className="p-3 text-sm text-danger">
            Unable to load alerts. Check the backend connection.
          </p>
        )}
        {!isLoading && !isError && !items.length && (
          <p className="p-3 text-sm text-muted-foreground">No incidents recorded yet.</p>
        )}
        <AnimatePresence initial={false}>
          {items.map((a: Alert) => {
            const Icon = iconMap[a.type] ?? AlertTriangle;
            return (
              <motion.div
                key={a.id}
                layout
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="group flex items-center gap-3 rounded-xl border border-border/60 bg-background/30 p-3 transition-colors hover:border-primary/40"
              >
                <div className={cn("rounded-lg border p-2", severityStyles[a.severity])}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold">{a.type}</p>
                    <span
                      className={cn(
                        "rounded-md border px-1.5 py-0.5 text-[10px] uppercase tracking-widest",
                        severityStyles[a.severity],
                      )}
                    >
                      {a.severity}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {a.camera ?? "Camera"} •{" "}
                    {formatDistanceToNow(new Date(a.timestamp), { addSuffix: true })}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
