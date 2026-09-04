import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const hours = Array.from({ length: 24 }).map((_, i) => ({
  hour: `${String(i).padStart(2, "0")}:00`,
  alerts: Math.floor(Math.random() * 24) + (i > 18 || i < 6 ? 10 : 2),
  detections: Math.floor(Math.random() * 80) + 20,
}));

const detectionStats = [
  { name: "Intrusion", value: 42 },
  { name: "Loitering", value: 28 },
  { name: "Running", value: 17 },
  { name: "Crowd", value: 35 },
  { name: "Unauth", value: 12 },
];

const tooltipStyle = {
  background: "oklch(0.18 0.02 250)",
  border: "1px solid oklch(0.78 0.18 230 / 40%)",
  borderRadius: 8,
  fontSize: 12,
};

export function AlertsPerHourChart() {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-widest">Alerts per Hour</h3>
        <p className="text-xs text-muted-foreground">Last 24 hours</p>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={hours}>
          <defs>
            <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="oklch(0.78 0.18 230)" stopOpacity={0.7} />
              <stop offset="95%" stopColor="oklch(0.78 0.18 230)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.32 0.04 250 / 40%)" />
          <XAxis dataKey="hour" stroke="oklch(0.7 0.02 250)" fontSize={10} interval={3} />
          <YAxis stroke="oklch(0.7 0.02 250)" fontSize={10} />
          <Tooltip contentStyle={tooltipStyle} />
          <Area
            type="monotone"
            dataKey="alerts"
            stroke="oklch(0.78 0.18 230)"
            fill="url(#g1)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DetectionStatsChart() {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-widest">Detection Statistics</h3>
        <p className="text-xs text-muted-foreground">By category</p>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={detectionStats}>
          <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.32 0.04 250 / 40%)" />
          <XAxis dataKey="name" stroke="oklch(0.7 0.02 250)" fontSize={10} />
          <YAxis stroke="oklch(0.7 0.02 250)" fontSize={10} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "oklch(0.78 0.18 230 / 10%)" }} />
          <Bar dataKey="value" fill="oklch(0.78 0.18 230)" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ActivityHeatmap() {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const cells = days.map((d) => ({
    day: d,
    values: Array.from({ length: 24 }).map(() => Math.random()),
  }));
  return (
    <div className="glass rounded-2xl p-5">
      <div className="mb-3">
        <h3 className="text-sm font-semibold uppercase tracking-widest">Activity Heatmap</h3>
        <p className="text-xs text-muted-foreground">Detections by hour & day</p>
      </div>
      <div className="space-y-1.5">
        {cells.map((row) => (
          <div key={row.day} className="flex items-center gap-2">
            <span className="w-8 text-[10px] uppercase text-muted-foreground">{row.day}</span>
            <div
              className="grid flex-1 grid-cols-24 gap-1"
              style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}
            >
              {row.values.map((v, i) => (
                <div
                  key={i}
                  className="aspect-square rounded-sm"
                  style={{ background: `oklch(0.78 0.18 230 / ${0.08 + v * 0.7})` }}
                  title={`${row.day} ${i}:00 — ${Math.round(v * 100)}`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
