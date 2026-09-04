import type { MissionEvidence, MissionTrackPoint } from "@/lib/api";

type Props = { track: MissionTrackPoint[]; evidence: MissionEvidence[] };

export function MissionTrackMap({ track, evidence }: Props) {
  const locatedEvidence = evidence.filter(
    (item) => item.latitude != null && item.longitude != null,
  );
  const points = [
    ...track.map((item) => ({ latitude: item.latitude, longitude: item.longitude })),
    ...locatedEvidence.map((item) => ({ latitude: item.latitude!, longitude: item.longitude! })),
  ];
  if (!points.length)
    return (
      <p className="text-sm text-muted-foreground">
        No real GPS samples are available for this mission.
      </p>
    );
  const latitudes = points.map((item) => item.latitude);
  const longitudes = points.map((item) => item.longitude);
  const minLat = Math.min(...latitudes),
    maxLat = Math.max(...latitudes),
    minLon = Math.min(...longitudes),
    maxLon = Math.max(...longitudes);
  const project = (latitude: number, longitude: number) => ({
    x: 20 + ((longitude - minLon) / (maxLon - minLon || 1)) * 360,
    y: 180 - ((latitude - minLat) / (maxLat - minLat || 1)) * 160,
  });
  const path = track
    .map((item) => project(item.latitude, item.longitude))
    .map((item, index) => `${index ? "L" : "M"}${item.x} ${item.y}`)
    .join(" ");
  return (
    <div className="rounded border bg-muted/20 p-2">
      <svg viewBox="0 0 400 200" className="w-full" role="img" aria-label="Mission track map">
        <rect x="0" y="0" width="400" height="200" fill="transparent" />
        <path d={path} fill="none" stroke="currentColor" strokeWidth="3" className="text-primary" />
        {locatedEvidence.map((item) => {
          const point = project(item.latitude!, item.longitude!);
          return (
            <circle
              key={item.id}
              cx={point.x}
              cy={point.y}
              r="6"
              className="fill-chart-5 stroke-background"
              strokeWidth="2"
            >
              <title>Evidence {item.id.slice(0, 8)}</title>
            </circle>
          );
        })}
      </svg>
      <p className="px-2 text-xs text-muted-foreground">
        Flight path and GPS-tagged evidence only. Evidence markers are hoverable.
      </p>
    </div>
  );
}
