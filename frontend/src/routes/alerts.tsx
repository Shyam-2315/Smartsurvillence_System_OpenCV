import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { AlertsPanel } from "@/components/dashboard/AlertsPanel";
import { ImagesGallery } from "@/components/dashboard/ImagesGallery";

export const Route = createFileRoute("/alerts")({
  head: () => ({ meta: [{ title: "Alerts — Sentinel AI" }, { name: "description", content: "Live alert feed and captured frames." }] }),
  component: AlertsPage,
});

function AlertsPage() {
  return (
    <DashboardLayout title="Alerts">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1 h-[640px]"><AlertsPanel /></div>
        <div className="lg:col-span-2"><ImagesGallery /></div>
      </div>
    </DashboardLayout>
  );
}
