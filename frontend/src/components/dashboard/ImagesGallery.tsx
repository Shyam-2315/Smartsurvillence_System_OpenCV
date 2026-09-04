import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Download, ImageOff, X, ZoomIn } from "lucide-react";
import { format } from "date-fns";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CapturedImage, fetchImages, imageUrl } from "@/lib/api";

export function ImagesGallery() {
  const { data, isLoading } = useQuery({
    queryKey: ["images"],
    queryFn: fetchImages,
    refetchInterval: 10000,
  });
  const [active, setActive] = useState<CapturedImage | null>(null);

  return (
    <div className="glass rounded-2xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-widest">Captured Frames</h3>
          <p className="text-xs text-muted-foreground">AI-flagged events</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {isLoading &&
          Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded-xl" />
          ))}
        {(data ?? []).map((img, i) => (
          <motion.button
            key={img.filename}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.02 }}
            whileHover={{ scale: 1.03 }}
            onClick={() => setActive(img)}
            className="group relative aspect-square overflow-hidden rounded-xl border border-border/60 bg-background/40"
          >
            <img
              src={imageUrl(img.filename)}
              alt={img.filename}
              className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
              onError={(e) => {
                const t = e.currentTarget;
                t.style.display = "none";
                t.parentElement?.classList.add("grid-bg");
                const fallback = t.parentElement?.querySelector(".fallback") as HTMLElement | null;
                if (fallback) fallback.style.display = "flex";
              }}
            />
            <div className="fallback absolute inset-0 hidden items-center justify-center text-muted-foreground">
              <ImageOff className="h-6 w-6" />
            </div>
            <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/0 to-transparent opacity-0 transition-opacity group-hover:opacity-100">
              <div className="absolute inset-x-0 bottom-0 flex items-center justify-between p-2">
                <span className="text-[10px] text-muted-foreground">
                  {format(new Date(img.timestamp), "HH:mm")}
                </span>
                <ZoomIn className="h-4 w-4 text-primary" />
              </div>
            </div>
          </motion.button>
        ))}
      </div>

      <Dialog open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <DialogContent className="max-w-4xl border-primary/30 bg-background/95 p-0">
          {active && (
            <div className="relative">
              <img
                src={imageUrl(active.filename)}
                alt={active.filename}
                className="max-h-[80vh] w-full rounded-md object-contain"
              />
              <div className="flex items-center justify-between border-t border-border/60 p-3">
                <div>
                  <p className="text-sm font-semibold">{active.type ?? "Capture"}</p>
                  <p className="text-xs text-muted-foreground">
                    {format(new Date(active.timestamp), "PPpp")}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button asChild variant="outline" size="sm">
                    <a href={imageUrl(active.filename)} download={active.filename}>
                      <Download className="mr-2 h-4 w-4" /> Download
                    </a>
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => setActive(null)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
