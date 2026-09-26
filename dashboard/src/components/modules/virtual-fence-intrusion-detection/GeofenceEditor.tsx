"use client";

import { useState, MouseEvent, useEffect } from "react";
import { ProposalModal } from "./ProposalModal";

export function GeofenceEditor({ cameraId, currentUser, initialHasPendingProposal = false, onResolve }: { cameraId: string, currentUser: string, initialHasPendingProposal?: boolean, onResolve?: () => void }) {
  const [isProposing, setIsProposing] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [hasPendingProposal, setHasPendingProposal] = useState(initialHasPendingProposal);

  // Instead of Lat/Lng, we now use percentages [x%, y%] of the video container
  const [activePolygon, setActivePolygon] = useState<[number, number][]>([]);

  const [proposedPolygon, setProposedPolygon] = useState<[number, number][]>([]);

  // Interactive Drawing State
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawnPoints, setDrawnPoints] = useState<[number, number][]>([]);

  // Deployment Countdown State
  const [isDeploying, setIsDeploying] = useState(false);
  const [countdown, setCountdown] = useState(3);
  
  const [isInitialized, setIsInitialized] = useState(false);

  const videoNum = parseInt(cameraId.split("_")[1], 10) || 1;

  // Fetch active fence on mount
  useEffect(() => {
    fetch('/api/fences')
      .then(res => res.json())
      .then(data => {
        if (data[cameraId] && data[cameraId].polygon) {
          setActivePolygon(data[cameraId].polygon);
        } else {
          setActivePolygon([[10, 10], [90, 10], [90, 90], [10, 90]]); // Default if none exists for this cam
        }
      })
      .catch(err => console.error("Failed to load fence:", err));
      
    // Fetch pending proposals on mount
    fetch('/api/proposals')
      .then(res => res.json())
      .then(data => {
        if (data[cameraId] && data[cameraId].polygon) {
          setHasPendingProposal(true);
          setProposedPolygon(data[cameraId].polygon);
        } else {
          setHasPendingProposal(false);
        }
      })
      .catch(err => console.error("Failed to load proposals:", err))
      .finally(() => setIsInitialized(true));
  }, [cameraId]);

  // Poll for external fence changes (e.g. Commander approved)
  useEffect(() => {
    if (!isInitialized || isDeploying) return;

    const interval = setInterval(() => {
      // Check for fence updates
      fetch('/api/fences')
        .then(res => res.json())
        .then(data => {
          if (data[cameraId] && data[cameraId].polygon) {
            const fetchedPolygon = data[cameraId].polygon;
            if (JSON.stringify(fetchedPolygon) !== JSON.stringify(activePolygon)) {
              // Fence was updated externally! Trigger local deployment countdown.
              setHasPendingProposal(false);
              setIsDeploying(true);
              setCountdown(3);
              
              let currentCount = 3;
              const deployInterval = setInterval(() => {
                currentCount -= 1;
                setCountdown(currentCount);
                if (currentCount <= 0) {
                  clearInterval(deployInterval);
                  setActivePolygon(fetchedPolygon);
                  setIsDeploying(false);
                  if (onResolve) onResolve();
                }
              }, 1000);
            }
          }
        })
        .catch(err => console.error("Failed to poll fence:", err));

      // Check if our proposal was rejected (vanished without fence changing)
      if (hasPendingProposal) {
        fetch('/api/proposals')
          .then(res => res.json())
          .then(data => {
            if (!data[cameraId]) {
              setHasPendingProposal(false);
              setDrawnPoints([]);
            }
          })
          .catch(err => console.error("Failed to poll proposals:", err));
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [cameraId, activePolygon, isInitialized, isDeploying, hasPendingProposal, onResolve]);

  const handleSvgClick = (e: MouseEvent<SVGSVGElement>) => {
    if (!isDrawing) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const xPercent = ((e.clientX - rect.left) / rect.width) * 100;
    const yPercent = ((e.clientY - rect.top) / rect.height) * 100;

    setDrawnPoints((prev: [number, number][]) => [...prev, [xPercent, yPercent]]);
  };

  const getPointsString = (points: [number, number][]) => {
    return points.map(p => `${p[0]},${p[1]}`).join(" ");
  };

  return (
    <div className="relative w-full h-full bg-black overflow-hidden group">
      {/* Video Feed */}
      <video 
        src={`/videos/${videoNum}.mp4`} 
        autoPlay 
        loop 
        muted 
        className="absolute inset-0 w-full h-full object-fill opacity-60"
        onError={(e) => {
          (e.target as HTMLElement).style.display = 'none';
        }}
      />
      
      {/* SVG Overlay for Polygons */}
      <svg 
        className={`absolute inset-0 w-full h-full z-10 ${isDrawing ? 'cursor-crosshair' : 'cursor-default'}`} 
        viewBox="0 0 100 100" 
        preserveAspectRatio="none"
        onClick={handleSvgClick}
      >
        {/* Draw Active Polygon if not drawing */}
        {!isDrawing && !hasPendingProposal && activePolygon.length > 2 && (
          <polygon 
            points={getPointsString(activePolygon)} 
            fill="var(--color-warning)" 
            fillOpacity="0.2" 
            stroke="var(--color-warning)" 
            strokeWidth="0.5" 
          />
        )}

        {/* Draw Proposed Polygon if reviewing */}
        {hasPendingProposal && proposedPolygon.length > 2 && (
          <polygon 
            points={getPointsString(proposedPolygon)} 
            fill="var(--color-critical)" 
            fillOpacity="0.3" 
            stroke="var(--color-critical)" 
            strokeWidth="0.5" 
            strokeDasharray="2,2"
          />
        )}

        {/* Live Drawing Polygon */}
        {isDrawing && drawnPoints.length > 0 && (
          <>
            {drawnPoints.length > 2 && (
              <polygon 
                points={getPointsString(drawnPoints)} 
                fill="var(--color-active)" 
                fillOpacity="0.2" 
                stroke="var(--color-active)" 
                strokeWidth="0.5" 
              />
            )}
            {/* Draw lines between points if less than 3 */}
            {drawnPoints.length === 2 && (
              <line 
                x1={drawnPoints[0][0]} y1={drawnPoints[0][1]} 
                x2={drawnPoints[1][0]} y2={drawnPoints[1][1]} 
                stroke="var(--color-active)" strokeWidth="0.5" 
              />
            )}
            {/* Draw vertices */}
             {drawnPoints.map((pt: [number, number], idx: number) => (
              <circle key={idx} cx={pt[0]} cy={pt[1]} r="1" fill="white" />
            ))}
          </>
        )}
      </svg>

      {/* Editor Overlay Controls */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-2">
        {hasPendingProposal ? (
          <button 
            onClick={() => setIsReviewing(true)}
            className="px-3 py-1 bg-[var(--color-critical)] text-white font-mono text-xs shadow-md border border-red-500 animate-pulse hover:bg-red-700"
          >
            REVIEW PENDING PROPOSAL
          </button>
        ) : isDrawing ? (
          <div className="flex gap-2">
            <button 
              onClick={() => {
                setDrawnPoints([]);
                setIsDrawing(false);
              }}
              className="px-4 py-2 bg-[var(--color-panel)] border border-[var(--color-hair)] text-[var(--color-muted)] text-sm hover:text-white transition-colors shadow-md"
            >
              Cancel
            </button>
            <button 
              onClick={() => {
                if (drawnPoints.length > 2) {
                  setProposedPolygon(drawnPoints);
                  setIsProposing(true);
                }
              }}
              disabled={drawnPoints.length < 3}
              className={`px-4 py-2 border text-sm transition-colors shadow-md ${drawnPoints.length > 2 ? 'bg-[var(--color-void)] border-[var(--color-active)] text-[var(--color-active)] hover:bg-[var(--color-active)] hover:text-black' : 'bg-[var(--color-panel)] border-[var(--color-hair)] text-[var(--color-muted)] cursor-not-allowed'}`}
            >
              Submit Drawing
            </button>
          </div>
        ) : (
          <button 
            onClick={() => {
              setDrawnPoints([]);
              setIsDrawing(true);
            }}
            className="px-4 py-2 bg-[var(--color-panel)] border border-[var(--color-hair)] text-[var(--color-primary)] text-sm hover:border-[var(--color-active)] transition-colors shadow-md"
          >
            + Draw New Fence
          </button>
        )}
      </div>

      {/* Deployment Countdown Overlay */}
      {isDeploying && (
        <div className="absolute inset-0 z-[600] flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="text-[var(--color-active)] font-mono text-xl mb-4 tracking-widest animate-pulse">
            DEPLOYING AUTHORIZED GEOFENCE...
          </div>
          <div className="text-white text-6xl font-mono font-bold">
            {countdown}
          </div>
        </div>
      )}

      {/* 2-Person Auth Proposal Modal */}
      {(isProposing || isReviewing) && !isDeploying && (
        <ProposalModal 
          mode={isProposing ? "propose" : "review"}
          currentUser={currentUser}
          cameraId={cameraId}
          activePolygon={activePolygon}
          proposedPolygon={proposedPolygon}
          onClose={() => {
            setIsProposing(false);
            setIsReviewing(false);
            // If they cancel out of proposing, keep them in drawing mode so they don't lose their work
            if (isProposing && drawnPoints.length > 2) {
                // Keep drawn points
            } else {
                setIsDrawing(false);
            }
          }}
          onSubmit={(action) => {
            if (action === "propose") {
              // Post proposal to backend
              fetch('/api/proposals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cameraId, polygon: proposedPolygon, action: "propose" })
              }).then(() => {
                setHasPendingProposal(true);
                setIsProposing(false);
                setIsReviewing(false);
                setIsDrawing(false);
              }).catch(err => console.error("Failed to propose:", err));
              
            } else if (action === "approve") {
              // Start Deployment Countdown
              setIsProposing(false);
              setIsReviewing(false);
              setIsDrawing(false);
              setIsDeploying(true);
              setCountdown(3);
              
              let currentCount = 3;
              const interval = setInterval(() => {
                currentCount -= 1;
                setCountdown(currentCount);
                if (currentCount <= 0) {
                  clearInterval(interval);
                  
                  // Clear proposal
                  fetch('/api/proposals', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cameraId, action: "clear" })
                  });

                  // Push to backend
                  fetch('/api/fences', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      cameraId: cameraId,
                      polygon: proposedPolygon,
                      severity: "critical"
                    })
                  })
                  .then(() => {
                    setHasPendingProposal(false);
                    setActivePolygon(proposedPolygon);
                    setDrawnPoints([]);
                    setIsDeploying(false);
                    if (onResolve) onResolve();
                  })
                  .catch(err => {
                    console.error("Failed to deploy fence:", err);
                    setIsDeploying(false);
                  });
                }
              }, 1000);
            } else if (action === "reject") {
              fetch('/api/proposals', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cameraId, action: "clear" })
              }).then(() => {
                setHasPendingProposal(false);
                setIsProposing(false);
                setIsReviewing(false);
                setIsDrawing(false);
                setDrawnPoints([]);
                if (onResolve) onResolve();
              });
            }
          }}
        />
      )}
    </div>
  );
}
