"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { GeofenceEditor } from "../../components/modules/virtual-fence-intrusion-detection/GeofenceEditor";
import { HumanDetectionFeed } from "../../components/modules/human_detection_tracking/HumanDetectionFeed";
import { VehicleDetectionFeed } from "../../components/modules/vehicle-detection-classification/VehicleDetectionFeed";
import { ANPRFeed } from "../../components/modules/anpr/ANPRFeed";
import { AlertRail, useAlertCards } from "../../components/AlertRail";
import dynamic from "next/dynamic";
import "leaflet/dist/leaflet.css";

const MapContainer = dynamic(() => import("react-leaflet").then(m => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then(m => m.TileLayer), { ssr: false });
const Marker = dynamic(() => import("react-leaflet").then(m => m.Marker), { ssr: false });
const Popup = dynamic(() => import("react-leaflet").then(m => m.Popup), { ssr: false });

const CAMERAS = [
  { id: "cam_01", label: "Human Module", lat: 34.085, lng: 74.03 },
  { id: "cam_02", label: "vehicle Module", lat: 34.090, lng: 74.035 },
  { id: "cam_03", label: "ANPR Module", lat: 34.095, lng: 74.04 },
  { id: "cam_04", label: "sus module", lat: 34.100, lng: 74.045 },
  { id: "cam_05", label: "Geofence Module", lat: 34.105, lng: 74.05 },
  { id: "cam_06", label: "Module 6", lat: 34.110, lng: 74.055 },
];

export default function CommanderDashboard() {
  const router = useRouter();
  const { alertCards, clearAlerts } = useAlertCards();
  const [pendingProposals, setPendingProposals] = useState<string[]>([]);
  const [selectedProposal, setSelectedProposal] = useState<string | null>(null);

  // Poll for new proposals
  useEffect(() => {
    const interval = setInterval(() => {
      fetch('/api/proposals')
        .then(res => res.json())
        .then(data => {
          // Virtual-fence approvals belong exclusively to CAM-05.
          setPendingProposals(Object.keys(data).filter((cameraId) => cameraId === "cam_05"));
        })
        .catch(err => console.error("Failed to load proposals:", err));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex-1 flex flex-row h-full">
      {/* Left Sidebar: Pending Authorizations */}
      <div className="w-64 shrink-0 border-r border-[var(--color-hair)] bg-[var(--color-panel)] flex flex-col">
        <div className="p-3 border-b border-[var(--color-hair)] uppercase tracking-wider text-[10px] font-semibold text-[var(--color-muted)] flex justify-between items-center">
          <span>Authorizations</span>
          <button onClick={() => router.push("/")} className="text-[var(--color-muted)] hover:text-white text-xs underline">Logout</button>
        </div>
        <div className="p-4 flex-1 text-sm overflow-y-auto space-y-3">

          {pendingProposals.length === 0 ? (
            <div className="text-[var(--color-muted)] text-center text-xs font-mono mt-4">
              NO PENDING AUTHORIZATIONS
            </div>
          ) : (
            pendingProposals.map((camId) => {
              const camDef = CAMERAS.find(c => c.id === camId);
              const label = camDef ? camDef.label : "Unknown Module";
              return (
                <div
                  key={camId}
                  onClick={() => setSelectedProposal(camId)}
                  className={`cursor-pointer p-3 border ${selectedProposal === camId ? "bg-[var(--color-void)] border-[var(--color-active)]" : "bg-[var(--color-panel)] border-[var(--color-hair)] hover:border-[var(--color-muted)]"}`}
                >
                  <div className="text-[var(--color-critical)] font-mono text-xs mb-1 animate-pulse">PENDING REVIEW</div>
                  <div className="text-[var(--color-primary)]">Geofence Edit</div>
                  <div className="text-[var(--color-muted)] text-xs mt-1">{camId.toUpperCase()} ({label})</div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Center Workspace: Commander Command Center */}
      <div className="flex-1 min-h-0 bg-[var(--color-void)] flex flex-col p-4 gap-4 overflow-hidden">

        {/* Top Half: Global Map & Camera Grid */}
        <div className="grid grid-cols-2 gap-4 h-[360px] shrink-0">

          {/* Global Map */}
          <div className="border border-[var(--color-hair)] bg-black relative flex flex-col">
            <div className="absolute top-0 left-0 right-0 p-2 z-[400] bg-black/60 font-mono text-xs text-[var(--color-muted)] border-b border-[var(--color-hair)] backdrop-blur-sm">
              GLOBAL SECTOR MAP
            </div>
            <div className="flex-1 relative z-0 [&_.leaflet-tile-pane]:brightness-[0.5] [&_.leaflet-tile-pane]:contrast-[1.2] [&_.leaflet-tile-pane]:saturate-[0.8]">
              <MapContainer center={[34.1, 74.04]} zoom={12} style={{ height: "100%", width: "100%" }} zoomControl={false}>
                <TileLayer url="https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_2vao_1_b41e552355ae400af5970986" />
                {CAMERAS.map(cam => (
                  <Marker key={cam.id} position={[cam.lat, cam.lng]}>
                    <Popup>{cam.id.toUpperCase()} ({cam.label})</Popup>
                  </Marker>
                ))}
              </MapContainer>
            </div>
          </div>

          {/* Camera Grid */}
          <div className="border border-[var(--color-hair)] bg-[var(--color-panel)] relative flex flex-col p-2 gap-2">
            <div className="font-mono text-xs text-[var(--color-muted)]">ACTIVE SECTOR FEEDS</div>
            <div className="flex-1 min-h-0 grid grid-cols-3 auto-rows-fr gap-2 overflow-hidden">
              {CAMERAS.map(cam => {
                const videoNum = parseInt(cam.id.split("_")[1], 10);
                const videoSrc = cam.id === "cam_04"
                  ? `/videos/4.1.mp4`
                  : `/videos/${videoNum}.mp4`;
                return (
                  <div key={cam.id} className="min-h-0 bg-black border border-[var(--color-hair)] relative flex items-center justify-center overflow-hidden">
                    <div className="absolute top-2 left-2 z-10 text-white font-mono text-[10px] bg-black/50 px-1 rounded">{cam.id.toUpperCase().replace("_", "-")}</div>
                    {cam.id === "cam_01" ? (
                      <HumanDetectionFeed compact />
                    ) : cam.id === "cam_02" ? (
                      <VehicleDetectionFeed compact />
                    ) : cam.id === "cam_03" ? (
                      <ANPRFeed compact />
                    ) : (
                      <>
                        <video
                          src={videoSrc}
                          autoPlay
                          loop
                          muted
                          className="w-full h-full object-contain opacity-80"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                            (e.target as HTMLElement).nextElementSibling?.classList.remove('hidden');
                          }}
                        />
                        <div className="text-[var(--color-muted)]/20 font-mono text-xs hidden absolute inset-0 flex items-center justify-center">NO SIGNAL</div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

        </div>

        {/* Bottom Half: Active Editor Pane */}
        <div className="flex-1 min-h-0 border border-[var(--color-hair)] bg-black relative flex flex-col overflow-hidden">
          <div className="absolute top-0 left-0 right-0 p-2 z-[400] bg-black/60 font-mono text-xs text-[var(--color-muted)] border-b border-[var(--color-hair)] backdrop-blur-sm">
            {selectedProposal ? `AUTHORIZATION WORKSPACE // ${selectedProposal.toUpperCase().replace("_", "-")}` : "AUTHORIZATION WORKSPACE"}
          </div>
          {selectedProposal && pendingProposals.includes(selectedProposal) ? (
            <div className="flex-1 min-h-0 relative mt-8 overflow-hidden">
              <GeofenceEditor
                key={selectedProposal}
                cameraId="cam_05"
                currentUser="commander_1"
                initialHasPendingProposal={true}
                onResolve={() => {
                  setPendingProposals(prev => prev.filter(p => p !== selectedProposal));
                  setSelectedProposal(null);
                }}
              />
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-[var(--color-muted)] font-mono text-sm mt-8">
              SELECT A PROPOSAL FROM THE QUEUE TO REVIEW
            </div>
          )}
        </div>

      </div>

      {/* Right Sidebar: Global Alert Rail (Commander View) */}
      <AlertRail
        alertCards={alertCards}
        showClearButton
        onClear={clearAlerts}
      />
    </div>
  );
}
