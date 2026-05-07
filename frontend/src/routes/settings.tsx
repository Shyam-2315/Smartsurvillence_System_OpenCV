import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/api";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — Sentinel AI" }, { name: "description", content: "Configure backend, AI detection, and notifications." }] }),
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <DashboardLayout title="Settings">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass space-y-4 rounded-2xl p-5">
          <h3 className="text-sm font-semibold uppercase tracking-widest">Backend</h3>
          <div className="space-y-2">
            <Label>FastAPI URL</Label>
            <Input defaultValue={API_BASE} />
          </div>
          <div className="space-y-2">
            <Label>Refresh interval (s)</Label>
            <Input type="number" defaultValue={3} />
          </div>
          <Button className="bg-primary text-primary-foreground hover:bg-primary/90">Save</Button>
        </div>
        <div className="glass space-y-4 rounded-2xl p-5">
          <h3 className="text-sm font-semibold uppercase tracking-widest">AI & Notifications</h3>
          {[
            ["GPU acceleration", true],
            ["Toast on new alerts", true],
            ["Auto-record on threat", true],
            ["Sound alerts", false],
          ].map(([label, val]) => (
            <div key={label as string} className="flex items-center justify-between rounded-lg border border-border/60 bg-background/30 p-3">
              <span className="text-sm">{label as string}</span>
              <Switch defaultChecked={val as boolean} />
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}
