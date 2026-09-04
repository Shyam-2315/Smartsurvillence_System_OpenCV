import { ReactNode } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { AppSidebar } from "./AppSidebar";
import { Bell, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export function DashboardLayout({ children, title }: { children: ReactNode; title: string }) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <AppSidebar />
        <div className="flex flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/70 px-4 backdrop-blur-xl">
            <SidebarTrigger />
            <div>
              <h1 className="text-sm font-semibold uppercase tracking-widest text-gradient-neon">
                {title}
              </h1>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <div className="relative hidden md:block">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search cameras, alerts…"
                  className="h-9 w-64 pl-8 bg-background/40"
                />
              </div>
              <button className="relative rounded-lg border border-border/60 bg-background/40 p-2 hover:border-primary/40">
                <Bell className="h-4 w-4" />
                <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-danger pulse-ring" />
              </button>
            </div>
          </header>
          <main className="flex-1 p-4 lg:p-6">{children}</main>
        </div>
      </div>
      <Toaster theme="dark" position="top-right" />
    </SidebarProvider>
  );
}
