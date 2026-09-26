"use client";

import { useState } from "react";


interface ProposalModalProps {
  mode: "propose" | "review";
  currentUser: string;
  cameraId: string;
  activePolygon: [number, number][];
  proposedPolygon: [number, number][];
  onClose: () => void;
  onSubmit: (action: "propose" | "approve" | "reject", reason?: string) => void;
}

export function ProposalModal({ mode, currentUser, cameraId, activePolygon, proposedPolygon, onClose, onSubmit }: ProposalModalProps) {
  const [severity, setSeverity] = useState("critical");
  const [schedule, setSchedule] = useState("always");
  const [rejectReason, setRejectReason] = useState("");

  const videoNum = parseInt(cameraId.split("_")[1], 10) || 1;

  // Simulated proposer to test the self-approval block
  const proposer = "operator_2"; // Set to operator_2 to trigger the self-approval block in review mode

  const getPointsString = (points: [number, number][]) => {
    return points.map(p => `${p[0]},${p[1]}`).join(" ");
  };

  return (
    <div className="fixed inset-0 z-[500] flex items-center justify-center bg-black/80">
      <div className="w-[500px] bg-[var(--color-panel)] border border-[var(--color-hair)] shadow-2xl flex flex-col">
        
        {/* Header */}
        <div className="p-4 border-b border-[var(--color-hair)] flex justify-between items-center">
          <h2 className="text-[var(--color-primary)] font-semibold">
            {mode === "propose" ? "Propose Geofence Change" : "Review Proposed Change"}
          </h2>
          <button onClick={onClose} className="text-[var(--color-muted)] hover:text-white">&times;</button>
        </div>

        {/* Diff / Map View Placeholder */}
        <div className="h-48 bg-black border-b border-[var(--color-hair)] relative overflow-hidden z-0">
          {/* Video Background */}
          <video 
            src={`/videos/${videoNum}.mp4`} 
            autoPlay 
            loop 
            muted 
            className="absolute inset-0 w-full h-full object-cover opacity-50 grayscale"
          />
          
          <svg className="absolute inset-0 w-full h-full z-10" viewBox="0 0 100 100" preserveAspectRatio="none">
            {/* Original Fence (Red, dashed to indicate removal) */}
            {activePolygon.length > 2 && (
              <polygon 
                points={getPointsString(activePolygon)} 
                fill="red" 
                fillOpacity="0.1" 
                stroke="red" 
                strokeWidth="0.5" 
                strokeDasharray="1,1" 
              />
            )}
            
            {/* Proposed Fence (Active color, solid) */}
            {proposedPolygon.length > 2 && (
              <polygon 
                points={getPointsString(proposedPolygon)} 
                fill="var(--color-active)" 
                fillOpacity="0.3" 
                stroke="var(--color-active)" 
                strokeWidth="0.8" 
              />
            )}
          </svg>
        </div>

        {/* Form Fields */}
        <div className="p-4 flex flex-col gap-4 text-sm">
          {mode === "review" && (
             <div className="mb-2 p-3 bg-[var(--color-void)] border border-[var(--color-hair)] text-[var(--color-primary)] font-mono text-xs">
                Changes: <br/>
                - Severity: warning → <span className="text-[var(--color-active)]">critical</span><br/>
                - Schedule: night-only → <span className="text-[var(--color-active)]">always</span>
             </div>
          )}

          <div className="flex flex-col gap-1">
            <label className="text-[var(--color-muted)] text-xs uppercase tracking-wider">Severity</label>
            <select 
              value={severity} 
              onChange={e => setSeverity(e.target.value)}
              disabled={mode === "review"}
              className="bg-[var(--color-void)] border border-[var(--color-hair)] text-[var(--color-primary)] p-2 outline-none focus:border-[var(--color-active)] disabled:opacity-50"
            >
              <option value="warning">Warning</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          
          <div className="flex flex-col gap-1">
            <label className="text-[var(--color-muted)] text-xs uppercase tracking-wider">Active Schedule</label>
            <select 
              value={schedule} 
              onChange={e => setSchedule(e.target.value)}
              disabled={mode === "review"}
              className="bg-[var(--color-void)] border border-[var(--color-hair)] text-[var(--color-primary)] p-2 outline-none focus:border-[var(--color-active)] disabled:opacity-50"
            >
              <option value="always">Always</option>
              <option value="night-only">Night-only</option>
            </select>
          </div>
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-[var(--color-hair)] bg-black/20 flex justify-end gap-3">
          {mode === "propose" ? (
            <>
              <button onClick={onClose} className="px-4 py-2 text-[var(--color-muted)] hover:text-white">Cancel</button>
              <button 
                onClick={() => onSubmit(currentUser.startsWith("commander") ? "approve" : "propose")} 
                className="px-4 py-2 bg-[var(--color-active)] text-black font-semibold"
              >
                {currentUser.startsWith("commander") ? "Apply Changes" : "Propose Change"}
              </button>
            </>
          ) : (
            currentUser === proposer ? (
              <span className="text-[var(--color-muted)] font-mono text-xs py-2 w-full text-center">
                Awaiting a different authorized reviewer.
              </span>
            ) : (
              <>
                <input 
                  type="text" 
                  placeholder="Reason for rejection..." 
                  className="flex-1 bg-[var(--color-void)] border border-[var(--color-hair)] text-[var(--color-primary)] px-2 text-sm"
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                />
                <button onClick={() => onSubmit("reject", rejectReason)} className="px-4 py-2 border border-[var(--color-hair)] text-[var(--color-muted)] hover:text-white">Reject</button>
                <button onClick={() => onSubmit("approve")} className="px-4 py-2 bg-[var(--color-active)] text-black font-semibold">Approve</button>
              </>
            )
          )}
        </div>
      </div>
    </div>
  );
}
