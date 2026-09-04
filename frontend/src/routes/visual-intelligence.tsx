import { useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Copy, ExternalLink, ScanSearch, Upload, WandSparkles } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  enhanceVisual,
  fetchVisualAnalysis,
  regionVisual,
  searchVisual,
  uploadVisualImage,
  VisualAnalysis,
  visualFileUrl,
} from "@/lib/api";

export const Route = createFileRoute("/visual-intelligence")({
  component: VisualIntelligencePage,
  validateSearch: (search: Record<string, unknown>) => ({
    analysisId: typeof search.analysisId === "string" ? search.analysisId : undefined,
  }),
  head: () => ({ meta: [{ title: "Visual Intelligence — Sentinel AI" }] }),
});

function VisualIntelligencePage() {
  const { analysisId } = Route.useSearch();
  const [analysis, setAnalysis] = useState<VisualAnalysis>();
  const [selecting, setSelecting] = useState(false);
  const [view, setView] = useState<"original" | "enhanced" | "ocr_overlay" | "object_overlay">(
    "original",
  );
  const [selectedOcr, setSelectedOcr] = useState("");
  const start = useRef<{ x: number; y: number } | null>(null);
  const image = useRef<HTMLImageElement>(null);
  const linkedAnalysis = useQuery({
    queryKey: ["visual-analysis", analysisId],
    queryFn: () => fetchVisualAnalysis(analysisId!),
    enabled: Boolean(analysisId),
  });
  useEffect(() => {
    if (linkedAnalysis.data) setAnalysis(linkedAnalysis.data);
  }, [linkedAnalysis.data]);
  const upload = useMutation({
    mutationFn: uploadVisualImage,
    onSuccess: setAnalysis,
    onError: () => toast.error("Image analysis failed. Check the file and server configuration."),
  });
  const enhance = useMutation({
    mutationFn: () =>
      enhanceVisual(analysis!.id, {
        auto_contrast: true,
        clahe: true,
        denoise: true,
        sharpen: 0.4,
        contrast: 1.1,
        upscale: 2,
      }),
    onSuccess: setAnalysis,
  });
  const region = useMutation({
    mutationFn: (r: { x: number; y: number; width: number; height: number }) =>
      regionVisual(analysis!.id, r),
    onSuccess: setAnalysis,
    onError: () => toast.error("Select a valid region inside the image."),
  });
  const webSearch = useMutation({
    mutationFn: (selected?: string) => searchVisual(analysis!.id, selected),
    onSuccess: setAnalysis,
    onError: () => toast.error("Web search could not be completed."),
  });
  const source =
    analysis &&
    visualFileUrl(
      view === "original"
        ? analysis.stored_original_path
        : analysis.metadata.derivatives?.[view] || analysis.stored_original_path,
    );
  const pointer = (e: React.PointerEvent<HTMLImageElement>) => {
    if (!selecting || !image.current) return;
    const r = image.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width,
      y = (e.clientY - r.top) / r.height;
    if (!start.current) start.current = { x, y };
    else {
      const s = start.current;
      start.current = null;
      setSelecting(false);
      region.mutate({
        x: Math.min(s.x, x),
        y: Math.min(s.y, y),
        width: Math.abs(x - s.x),
        height: Math.abs(y - s.y),
      });
    }
  };
  return (
    <DashboardLayout title="Visual Intelligence">
      <div className="space-y-4">
        <Card>
          <CardContent className="flex flex-wrap items-center gap-3 p-4">
            <label>
              <input
                className="hidden"
                type="file"
                accept=".jpg,.jpeg,.png,.webp"
                onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])}
              />
              <Button asChild disabled={upload.isPending}>
                <span>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload Image
                </span>
              </Button>
            </label>
            <span className="text-sm text-muted-foreground">
              Non-biometric evidence analysis. Original evidence is preserved unchanged.
            </span>
          </CardContent>
        </Card>
        {!analysis ? (
          <Card>
            <CardContent className="py-16 text-center text-muted-foreground">
              <ScanSearch className="mx-auto mb-3 h-10 w-10" />
              Upload a surveillance image to begin an investigation.
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {view === "original" ? "ORIGINAL EVIDENCE" : "ENHANCED / ANALYSIS DERIVATIVE"}{" "}
                    {view !== "original" && (
                      <span className="ml-2 text-xs font-normal text-amber-400">
                        Derivative; not a reconstruction of missing detail
                      </span>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="mb-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant={view === "original" ? "default" : "outline"}
                      onClick={() => setView("original")}
                    >
                      Original
                    </Button>
                    {analysis.metadata.derivatives?.enhanced && (
                      <Button
                        size="sm"
                        variant={view === "enhanced" ? "default" : "outline"}
                        onClick={() => setView("enhanced")}
                      >
                        Enhanced
                      </Button>
                    )}
                    {analysis.metadata.derivatives?.ocr_overlay && (
                      <Button
                        size="sm"
                        variant={view === "ocr_overlay" ? "default" : "outline"}
                        onClick={() => setView("ocr_overlay")}
                      >
                        OCR overlay
                      </Button>
                    )}
                    {analysis.metadata.derivatives?.object_overlay && (
                      <Button
                        size="sm"
                        variant={view === "object_overlay" ? "default" : "outline"}
                        onClick={() => setView("object_overlay")}
                      >
                        Object overlay
                      </Button>
                    )}
                  </div>
                  <img
                    ref={image}
                    onPointerUp={pointer}
                    src={source}
                    className={`max-h-[560px] w-full object-contain ${selecting ? "cursor-crosshair" : ""}`}
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    {analysis.original_filename} · {analysis.width}×{analysis.height} · SHA-256{" "}
                    {analysis.sha256}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Button
                    className="w-full"
                    onClick={() => enhance.mutate()}
                    disabled={enhance.isPending}
                  >
                    <WandSparkles className="mr-2 h-4 w-4" />
                    Enhance
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={() => setSelecting(true)}
                    disabled={region.isPending}
                  >
                    Select Region
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    {selecting
                      ? "Click two corners of the evidence image."
                      : analysis.metadata.evidence_notice}
                  </p>
                </CardContent>
              </Card>
            </div>
            <Tabs defaultValue="overview">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="ocr">OCR</TabsTrigger>
                <TabsTrigger value="objects">Objects</TabsTrigger>
                <TabsTrigger value="web">Web Intelligence</TabsTrigger>
                <TabsTrigger value="report">Report</TabsTrigger>
              </TabsList>
              <TabsContent value="overview">
                <Evidence
                  title="Extracted clues"
                  values={Object.entries(analysis.entities).flatMap(([k, v]) =>
                    (v || []).map((x) => `${k}: ${x}`),
                  )}
                />
              </TabsContent>
              <TabsContent value="ocr">
                <Card>
                  <CardContent className="space-y-2 pt-5">
                    {analysis.metadata.ocr_notice && (
                      <p className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-sm text-amber-200">
                        {analysis.metadata.ocr_notice}
                      </p>
                    )}
                    <p className="rounded border border-border p-2 text-sm">
                      <strong>{analysis.metadata.ocr_status?.state || "OCR Ready"}</strong>
                      {" — "}
                      {analysis.metadata.ocr_status?.message}
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        navigator.clipboard.writeText(analysis.ocr.map((x) => x.text).join("\n"))
                      }
                    >
                      <Copy className="mr-2 h-3 w-3" />
                      Copy Text
                    </Button>
                    {analysis.ocr.map((item, i) => (
                      <div key={i} className="flex justify-between border-b border-border py-2">
                        <label className="flex items-center gap-2">
                          <input
                            type="radio"
                            name="ocr"
                            checked={selectedOcr === item.text}
                            onChange={() => setSelectedOcr(item.text)}
                          />
                          <span>{item.text}</span>
                        </label>
                        <span className="text-muted-foreground">
                          {Math.round(item.confidence * 100)}% · {JSON.stringify(item.box)}
                        </span>
                      </div>
                    )) || "No OCR engine is configured or no readable text was found."}
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="objects">
                <Evidence
                  title="Detected objects"
                  values={analysis.detections.map(
                    (x) => `${x.class} — ${Math.round(x.confidence * 100)}%`,
                  )}
                />
              </TabsContent>
              <TabsContent value="web">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">WEB INTELLIGENCE</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm">
                      Status:{" "}
                      <strong>
                        {analysis.summary.web_intelligence?.status?.status || "Disabled"}
                      </strong>
                      {analysis.summary.web_intelligence?.status?.reason &&
                        ` — ${analysis.summary.web_intelligence.status.reason}`}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        onClick={() => webSearch.mutate()}
                        disabled={webSearch.isPending}
                      >
                        Generate Search Queries / Search Again
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!selectedOcr || webSearch.isPending}
                        onClick={() => webSearch.mutate(selectedOcr)}
                      >
                        Search Selected OCR Text
                      </Button>
                    </div>
                    <div>
                      <h3 className="mb-2 font-medium">Generated Queries</h3>
                      {analysis.search_queries.map((x, i) => (
                        <div key={i} className="border-b py-2">
                          <strong>
                            Query #{i + 1}: {x.query}
                          </strong>
                          <p className="text-xs text-muted-foreground">
                            Evidence strength:{" "}
                            {x.score >= 0.78 ? "High" : x.score >= 0.58 ? "Medium" : "Low"} ·{" "}
                            {x.evidence.join(" · ")}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div>
                      <h3 className="mb-2 font-medium">Sources</h3>
                      {analysis.web_results.map((x, i) => (
                        <div key={i} className="border-b py-2">
                          <p>
                            <strong>
                              [{x.source_type || "unknown"}] {x.title}
                            </strong>
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {x.domain} — {x.snippet}
                          </p>
                          <a
                            className="inline-flex items-center gap-1 text-sm text-primary"
                            href={x.url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            Open source <ExternalLink className="h-3 w-3" />
                          </a>
                        </div>
                      ))}
                    </div>
                    <div>
                      <h3 className="mb-2 font-medium">Candidate Matches</h3>
                      {analysis.summary.correlation?.inferred?.candidate_matches?.map((x, i) => (
                        <div key={i} className="border-b py-2">
                          <strong>{x.name}</strong>
                          <p>Confidence: {x.confidence}</p>
                          {x.supporting_evidence.map((e, j) => (
                            <p key={j} className="text-sm">
                              ✓ {e}
                            </p>
                          ))}
                        </div>
                      ))}
                      {analysis.summary.correlation?.inferred?.contradictions?.map((x, i) => (
                        <p key={i} className="text-sm text-amber-400">
                          {x}
                        </p>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="report">
                <Evidence
                  title="Assessment"
                  values={[
                    analysis.summary.assessment?.summary || "",
                    `Confidence: ${analysis.summary.assessment?.confidence || "low"}`,
                    ...(analysis.summary.assessment?.limitations || []),
                  ]}
                />
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
function Evidence({ title, values }: { title: string; values: string[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {values.length ? (
          <ul className="space-y-2 text-sm">
            {values.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No evidence available.</p>
        )}
      </CardContent>
    </Card>
  );
}
