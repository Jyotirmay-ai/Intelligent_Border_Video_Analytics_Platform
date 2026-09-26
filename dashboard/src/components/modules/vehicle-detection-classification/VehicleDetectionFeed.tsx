"use client";

import { useEffect, useState } from "react";

export function VehicleDetectionFeed({ compact = false }: { compact?: boolean }) {
  const [version, setVersion] = useState(0);
  const [sources, setSources] = useState<Array<{ value: string; label: string }>>([]);
  const [source, setSource] = useState("data/sample_videos/3.1.mp4");
  useEffect(() => {
    const timer = window.setInterval(() => setVersion(Date.now()), 150);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (compact) return;
    fetch("/api/vehicle-source")
      .then((response) => response.json())
      .then((data) => {
        if (Array.isArray(data.sources)) setSources(data.sources);
        if (typeof data.selectedSource === "string") setSource(data.selectedSource);
      })
      .catch((error) => console.error("Unable to load CAM-02 sources:", error));
  }, [compact]);

  const changeSource = async (nextSource: string) => {
    setSource(nextSource);
    await fetch("/api/vehicle-source", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: nextSource }),
    });
  };

  return (
    <div className="relative h-full min-h-0 w-full overflow-hidden bg-black">
      <img src={`/processed/cam_02.jpg?v=${version}`} alt="CAM-02 vehicle detection output" className="absolute inset-0 h-full w-full object-contain" />
      <div className={`absolute ${compact ? "bottom-1 left-1" : "top-4 left-4"} border border-[var(--color-active)] bg-black/75 px-2 py-1 font-mono text-[10px] text-[var(--color-active)]`}>
        {compact ? "VEHICLE AI" : "CAM-02 // VEHICLE DETECTION & CLASSIFICATION"}
      </div>
      {!compact && <div className="absolute right-4 top-4 border border-[var(--color-hair)] bg-black/75 p-3 font-mono text-xs backdrop-blur-sm">
        <div className="mb-2 text-[var(--color-primary)]">SOURCE FEED</div>
        <select value={source} onChange={(event) => changeSource(event.target.value)} className="w-32 border border-[var(--color-hair)] bg-black p-1 text-[var(--color-active)] outline-none" aria-label="CAM-02 source feed">
          {sources.length === 0 ? <option value={source}>Video 3.1</option> : sources.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </div>}
      {!compact && <div className="absolute bottom-4 left-4 border border-[var(--color-hair)] bg-black/75 p-3 font-mono text-xs text-[var(--color-muted)]">YOLO + ByteTrack • vehicle crops saved locally</div>}
    </div>
  );
}
