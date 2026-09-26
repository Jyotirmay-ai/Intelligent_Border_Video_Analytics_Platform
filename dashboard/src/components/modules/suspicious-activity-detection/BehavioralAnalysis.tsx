"use client";

import { useState, useEffect } from "react";

interface TrackedObject {
  objectId: string;
  startTime: number;
  dwellTime: number;
  status: "monitoring" | "suspicious";
}

export function BehavioralAnalysis({ cameraId }: { cameraId: string }) {
  const [objects, setObjects] = useState<TrackedObject[]>([]);
  const [dwellThreshold, setDwellThreshold] = useState(10);
  const [isConnected, setIsConnected] = useState(false);
  const [currentVideo, setCurrentVideo] = useState("");
  const [behavioralVideos, setBehavioralVideos] = useState<string[]>([]);

  useEffect(() => {
    // Dynamically fetch the list of behavioral videos from the API
    fetch('/api/videos/behavioral')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setBehavioralVideos(data);
          if (data.length > 0) {
            setCurrentVideo(data[0]);
          }
        }
      })
      .catch(err => console.error("Failed to fetch behavioral videos:", err));
  }, []);

  useEffect(() => {
    setIsConnected(true);
    
    const interval = setInterval(() => {
      setObjects((prev: TrackedObject[]) => {
        if (prev.length === 0) {
          return [{
            objectId: "OBJ-SAD-99",
            startTime: Date.now(),
            dwellTime: 0,
            status: "monitoring"
          }];
        }
        
        return prev.map((obj: TrackedObject) => {
          const newDwell = obj.dwellTime + 1;
          return {
            ...obj,
            dwellTime: newDwell,
            status: newDwell >= dwellThreshold ? "suspicious" : "monitoring"
          };
        });
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [dwellThreshold]);

  return (
    <div className="relative w-full h-full bg-black overflow-hidden group">
      {/* Video Feed */}
      <video 
        key={currentVideo}
        src={`/videos/${currentVideo}`} 
        autoPlay 
        loop 
        muted 
        className="absolute inset-0 w-full h-full object-cover opacity-60"
      />
      
      {/* Analysis Overlay */}
      <div className="absolute inset-0 z-10 pointer-events-none flex flex-col p-6">
        <div className="flex justify-between items-start">
          <div className="bg-black/70 border border-[var(--color-hair)] p-3 backdrop-blur-sm">
            <h3 className="text-[var(--color-primary)] font-mono text-xs uppercase tracking-tighter mb-2">
              Behavioral Analysis Engine
            </h3>
            <div className="space-y-2">
               {objects.map((obj: TrackedObject) => (
                <div key={obj.objectId} className="flex items-center gap-3 font-mono text-xs">
                  <div className={`w-2 h-2 rounded-full ${obj.status === 'suspicious' ? 'bg-red-500 animate-pulse' : 'bg-green-500'}`} />
                  <span className="text-[var(--color-muted)]">{obj.objectId}:</span>
                  <span className={obj.status === 'suspicious' ? 'text-red-500' : 'text-white'}>
                    {obj.dwellTime}s
                  </span>
                  <span className="text-[10px] opacity-50">
                    {obj.status === 'suspicious' ? '[LOITERING]' : '[TRACKING]'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3">
            {/* Video Selector */}
            <div className="bg-black/70 border border-[var(--color-hair)] p-3 backdrop-blur-sm pointer-events-auto">
              <h3 className="text-[var(--color-primary)] font-mono text-xs uppercase tracking-tighter mb-2">
                Source Feed
              </h3>
              <select 
                value={currentVideo}
                onChange={(e) => setCurrentVideo(e.target.value)}
                className="bg-black border border-[var(--color-hair)] text-[var(--color-active)] font-mono text-xs p-1 w-full outline-none cursor-pointer"
              >
                {behavioralVideos.map((vid: string) => (
                  <option key={vid} value={vid} className="bg-[var(--color-void)]">
                    Video {vid.replace('.mp4', '')}
                  </option>
                ))}
              </select>
            </div>

            {/* Rule Config */}
            <div className="bg-black/70 border border-[var(--color-hair)] p-3 backdrop-blur-sm pointer-events-auto">
              <h3 className="text-[var(--color-primary)] font-mono text-xs uppercase tracking-tighter mb-2">
                Rule Config
              </h3>
              <div className="flex flex-col gap-2">
                <label className="text-[var(--color-muted)] text-[10px] font-mono">DWELL THRESHOLD (S)</label>
                <input 
                  type="number" 
                  value={dwellThreshold} 
                  onChange={(e) => setDwellThreshold(parseInt(e.target.value) || 0)}
                  className="bg-black border border-[var(--color-hair)] text-[var(--color-active)] font-mono text-xs p-1 w-20 outline-none"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Status Bar */}
        <div className="mt-auto flex justify-between items-end">
          <div className="bg-black/70 border border-[var(--color-hair)] p-2 backdrop-blur-sm">
            <div className="text-[var(--color-muted)] font-mono text-[10px]">
              STATUS: {isConnected ? "CONNECTED" : "DISCONNECTED"}
            </div>
            <div className="text-[var(--color-active)] font-mono text-[10px]">
              STREAM: CAM_04_BEHAVIORAL ({currentVideo})
            </div>
          </div>
          <div className="text-right">
            <div className="text-white font-mono text-xs opacity-30">SAD-ENGINE v1.0.4</div>
          </div>
        </div>
      </div>
    </div>
  );
}
