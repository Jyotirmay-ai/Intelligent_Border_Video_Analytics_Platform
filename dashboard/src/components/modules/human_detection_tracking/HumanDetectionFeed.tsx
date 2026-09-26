"use client";

import { useEffect, useState } from "react";

export function HumanDetectionFeed({ compact = false }: { compact?: boolean }) {
  const [frameVersion, setFrameVersion] = useState<number | null>(null);
  const [sources, setSources] = useState<Array<{ value: string; label: string }>>([]);
  const [source, setSource] = useState("data/sample_videos/1.1.mp4");
  const [isSwitching, setIsSwitching] = useState(false);

  useEffect(() => {
    setFrameVersion(Date.now());
    const interval = window.setInterval(() => setFrameVersion(Date.now()), 120);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (compact) return;
    fetch("/api/human-source")
      .then((response) => response.json())
      .then((data) => {
        if (Array.isArray(data.sources)) setSources(data.sources);
        if (typeof data.selectedSource === "string") setSource(data.selectedSource);
      })
      .catch((error) => console.error("Unable to load CAM-01 sources:", error));
  }, [compact]);

  const changeSource = async (nextSource: string) => {
    setSource(nextSource);
    setIsSwitching(true);
    try {
      const response = await fetch("/api/human-source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: nextSource }),
      });
      if (!response.ok) throw new Error("Source update failed");
    } catch (error) {
      console.error("Unable to change CAM-01 source:", error);
    } finally {
      window.setTimeout(() => setIsSwitching(false), 700);
    }
  };

  if (frameVersion === null) {
    return (
      <div className="relative h-full min-h-0 w-full overflow-hidden bg-black">
        <div className="absolute inset-0 flex items-center justify-center text-white/20 font-mono text-xs">
          LOADING FEED...
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-0 w-full overflow-hidden bg-black">
      <img
        src={`/processed/cam_01.jpg?v=${frameVersion}`}
        alt="CAM-01 human detection output"
        className="absolute inset-0 h-full w-full object-contain"
        onError={(event) => {
          event.currentTarget.style.display = "none";
        }}
      />
      <div className={`absolute ${compact ? "bottom-1 left-1" : "top-4 left-4"} border border-[var(--color-active)] bg-black/75 px-2 py-1 font-mono text-[10px] text-[var(--color-active)]`}>
        {compact ? "HUMAN AI" : "CAM-01 // HUMAN DETECTION & FACE ANALYSIS"}
      </div>
      {!compact && (
        <>
          <div className="absolute right-4 top-4 border border-[var(--color-hair)] bg-black/75 p-3 font-mono text-xs backdrop-blur-sm">
            <div className="mb-2 text-[var(--color-primary)]">SOURCE FEED</div>
            <select
              value={source}
              onChange={(event) => changeSource(event.target.value)}
              className="w-32 border border-[var(--color-hair)] bg-black p-1 text-[var(--color-active)] outline-none"
              aria-label="CAM-01 source feed"
            >
              {sources.length === 0 ? (
                <option value={source}>Video 1.1</option>
              ) : sources.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            {isSwitching && <div className="mt-1 text-[9px] text-[var(--color-muted)]">SWITCHING...</div>}
          </div>
          <div className="absolute bottom-4 left-4 border border-[var(--color-hair)] bg-black/75 p-3 font-mono text-xs text-[var(--color-primary)]">
            <div className="text-[var(--color-active)]">STATUS: PROCESSING</div>
            <div className="mt-1 text-[var(--color-muted)]">YOLO person detection • YuNet face analysis</div>
          </div>
        </>
      )}
    </div>
  );
}
