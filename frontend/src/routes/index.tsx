import { createFileRoute } from "@tanstack/react-router";
import { Camera, BellRing, Users, Activity, Cpu } from "lucide-react";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { StatCard } from "@/components/dashboard/StatCard";
import { LiveCamera } from "@/components/dashboard/LiveCamera";
import { AlertsPanel } from "@/components/dashboard/AlertsPanel";
import { AIStatusBar } from "@/components/dashboard/AIStatusBar";
import { AlertsPerHourChart, DetectionStatsChart } from "@/components/dashboard/Charts";
import { ImagesGallery } from "@/components/dashboard/ImagesGallery";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sentinel AI — Smart Surveillance Dashboard" },
      {
        name: "description",
        content:
          "Real-time AI-powered surveillance dashboard with live camera feeds, alerts, and analytics.",
      },
      { property: "og:title", content: "Sentinel AI — Smart Surveillance Dashboard" },
      {
        property: "og:description",
        content: "Real-time AI-powered surveillance with live feeds, alerts, and analytics.",
      },
    ],
  }),
  component: DashboardPage,
});

function DashboardPage() {
  return (
    <DashboardLayout title="Command Center">
      <div className="space-y-4">
        <AIStatusBar />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard
            label="Active Cameras"
            value={8}
            icon={Camera}
            trend="+2 since yesterday"
            accent="primary"
          />
          <StatCard
            label="Alerts Today"
            value={47}
            icon={BellRing}
            trend="12 in last hour"
            accent="warning"
          />
          <StatCard
            label="People Detected"
            value={312}
            icon={Users}
            trend="Peak: 18:00"
            accent="primary"
          />
          <StatCard
            label="System Status"
            value="Online"
            icon={Activity}
            trend="99.98% uptime"
            accent="success"
          />
          <StatCard label="GPU Status" value="73%" icon={Cpu} trend="CUDA • 8GB" accent="primary" />
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <LiveCamera />
          </div>
          <div className="h-[520px]">
            <AlertsPanel limit={12} />
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <AlertsPerHourChart />
          <DetectionStatsChart />
        </div>

        <ImagesGallery />
      </div>
    </DashboardLayout>
  );
}
