import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Video,
  BellRing,
  BarChart3,
  Settings,
  ShieldCheck,
  ScanSearch,
  Plane,
  Clapperboard,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
  SidebarFooter,
} from "@/components/ui/sidebar";
import { useAuth } from "@/lib/auth";

const items = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Live Monitoring", url: "/live", icon: Video },
  { title: "Airborne", url: "/airborne", icon: Plane },
  { title: "Recorded Missions", url: "/recorded-missions", icon: Clapperboard },
  { title: "Alerts", url: "/alerts", icon: BellRing },
  { title: "Analytics", url: "/analytics", icon: BarChart3 },
  { title: "Visual Intelligence", url: "/visual-intelligence", icon: ScanSearch },
  { title: "Settings", url: "/settings", icon: Settings },
];

export function AppSidebar() {
  const { enabled, logout } = useAuth();
  const path = useRouterState({ select: (s) => s.location.pathname });
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-3">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-chart-5 neon-glow">
            <ShieldCheck className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="flex flex-col leading-tight group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-bold tracking-wide text-gradient-neon">SENTINEL AI</span>
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Surveillance Suite
            </span>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => {
                const active = path === item.url;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild isActive={active}>
                      <Link to={item.url} className="flex items-center gap-2">
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
          <span className="h-2 w-2 rounded-full bg-success pulse-ring" />
          {enabled ? <button onClick={logout}>Sign out</button> : "Local access"}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
