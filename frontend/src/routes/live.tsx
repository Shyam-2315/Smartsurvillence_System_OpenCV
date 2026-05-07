import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { LiveCamera } from "@/components/dashboard/LiveCamera";
import { AIStatusBar } from "@/components/dashboard/AIStatusBar";
import { AlertsPanel } from "@/components/dashboard/AlertsPanel";

export const Route = createFileRoute("/live")({
  head: () => ({ meta: [{ title: "Live Monitoring — Sentinel AI" }, { name: "description", content: "Real-time camera feeds with AI detection." }] }),
  component: LivePage,
});

function LivePage() {
  return (
    <DashboardLayout title="Live Monitoring">
      <div className="space-y-4">
        <AIStatusBar />
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2"><LiveCamera /></div>
          <div className="h-[560px]"><AlertsPanel limit={20} /></div>
        </div>
      </div>
    </DashboardLayout>
  );
}
