import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  accent?: "primary" | "success" | "warning" | "danger";
}

const accentMap = {
  primary: "from-primary/30 to-primary/0 text-primary",
  success: "from-success/30 to-success/0 text-success",
  warning: "from-warning/30 to-warning/0 text-warning",
  danger: "from-danger/30 to-danger/0 text-danger",
};

export function StatCard({ label, value, icon: Icon, trend, accent = "primary" }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -3 }}
      className="glass relative overflow-hidden rounded-2xl p-5"
    >
      <div
        className={cn(
          "absolute -right-8 -top-8 h-32 w-32 rounded-full bg-gradient-to-br blur-2xl",
          accentMap[accent],
        )}
      />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight">{value}</p>
          {trend && <p className="mt-1 text-xs text-muted-foreground">{trend}</p>}
        </div>
        <div
          className={cn(
            "rounded-xl border border-border/60 bg-background/40 p-2.5",
            accentMap[accent].split(" ").slice(-1),
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </motion.div>
  );
}
