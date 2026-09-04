import { createFileRoute } from "@tanstack/react-router";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchLoiterRule, fetchZones, saveLoiterRule } from "@/lib/api";
import { useEffect, useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — Sentinel AI" },
      { name: "description", content: "Configure backend, AI detection, and notifications." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const qc = useQueryClient();
  const { data: zones } = useQuery({
    queryKey: ["zones"],
    queryFn: fetchZones,
    refetchInterval: 10000,
  });
  const { data: rule } = useQuery({
    queryKey: ["rule-loitering"],
    queryFn: fetchLoiterRule,
    refetchInterval: 10000,
  });

  const [enabled, setEnabled] = useState(true);
  const [minDuration, setMinDuration] = useState("10");
  const [cooldown, setCooldown] = useState("30");
  const [zoneId, setZoneId] = useState<string>("all");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!rule || dirty) return;
    setEnabled(rule.enabled);
    setMinDuration(String(rule.min_duration_sec));
    setCooldown(String(rule.cooldown_sec));
    setZoneId(rule.zone_id === null ? "all" : String(rule.zone_id));
  }, [rule, dirty]);

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
          <h3 className="text-sm font-semibold uppercase tracking-widest">AI Rules (Loitering)</h3>
          <div className="space-y-2">
            <Label>Enable loitering alerts</Label>
            <div className="flex items-center justify-between rounded-lg border border-border/60 bg-background/30 p-3">
              <span className="text-sm text-muted-foreground">
                Alert when a tracked person stays too long
              </span>
              <Switch
                checked={enabled}
                onCheckedChange={(v) => {
                  setDirty(true);
                  setEnabled(v);
                }}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Min duration (sec)</Label>
              <Input
                value={minDuration}
                type="number"
                min={1}
                max={600}
                onChange={(e) => {
                  setDirty(true);
                  setMinDuration(e.target.value);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>Cooldown (sec)</Label>
              <Input
                value={cooldown}
                type="number"
                min={0}
                max={3600}
                onChange={(e) => {
                  setDirty(true);
                  setCooldown(e.target.value);
                }}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Zone</Label>
            <Select
              value={zoneId}
              onValueChange={(v) => {
                setDirty(true);
                setZoneId(v);
              }}
            >
              <SelectTrigger className="bg-background/30">
                <SelectValue placeholder="Choose a zone" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All zones (no filter)</SelectItem>
                {(zones ?? []).map((z) => (
                  <SelectItem key={z.id} value={String(z.id)}>
                    {z.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Zones are normalized (0..1) polygons. Default: Full Frame.
            </p>
          </div>
          <Button
            className="bg-primary text-primary-foreground hover:bg-primary/90"
            onClick={async () => {
              const payload = {
                enabled,
                min_duration_sec: Number(minDuration || 10),
                cooldown_sec: Number(cooldown || 30),
                zone_id: zoneId === "all" ? null : Number(zoneId),
              };
              await saveLoiterRule(payload);
              await qc.invalidateQueries({ queryKey: ["rule-loitering"] });
              setDirty(false);
            }}
          >
            Save Rule
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}
