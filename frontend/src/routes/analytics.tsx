import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import {
  ActivityHeatmap,
  AlertsPerHourChart,
  DetectionStatsChart,
} from "@/components/dashboard/Charts";

export const Route = createFileRoute("/analytics")({
  head: () => ({
    meta: [
      { title: "Analytics — Sentinel AI" },
      {
        name: "description",
        content: "Surveillance analytics, detection stats, and activity heatmaps.",
      },
    ],
  }),
  component: AnalyticsPage,
});

function AnalyticsPage() {
  return (
    <DashboardLayout title="Analytics">
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <AlertsPerHourChart />
          <DetectionStatsChart />
        </div>
        <ActivityHeatmap />
      </div>
    </DashboardLayout>
  );
}
