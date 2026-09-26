"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { GeofenceEditor } from "../components/modules/virtual-fence-intrusion-detection/GeofenceEditor";
import { BehavioralAnalysis } from "../components/modules/suspicious-activity-detection/BehavioralAnalysis";
import { HumanDetectionFeed } from "../components/modules/human_detection_tracking/HumanDetectionFeed";
import { VehicleDetectionFeed } from "../components/modules/vehicle-detection-classification/VehicleDetectionFeed";
import { ANPRFeed } from "../components/modules/anpr/ANPRFeed";
import { AlertRail, useAlertCards } from "../components/AlertRail";
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

export default function Home() {
  const router = useRouter();
  const [selectedCamera, setSelectedCamera] = useState("cam_01");
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [passcode, setPasscode] = useState("");
  const [loginError, setLoginError] = useState("");
  const { alertCards } = useAlertCards();

  const handleLoginSubmit = () => {
    if (passcode === "ALPHA-7") {
      router.push("/commander");
    } else {
      setLoginError("Invalid Passcode.");
      setPasscode("");
    }
  };

  return (
    <div className="flex-1 flex flex-row h-full">
      {/* Passcode Login Modal */}
      {isLoginModalOpen && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80">
          <div className="w-[400px] bg-[var(--color-panel)] border border-[var(--color-hair)] p-6 shadow-2xl flex flex-col gap-4">
            <h2 className="text-[var(--color-primary)] font-semibold uppercase tracking-wider text-sm">Commander Authorization</h2>
            {loginError && <div className="text-[var(--color-critical)] text-xs font-mono">{loginError}</div>}
            <input
              type="password"
              placeholder="ENTER PASSCODE"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLoginSubmit()}
              className="bg-[var(--color-void)] border border-[var(--color-hair)] text-[var(--color-active)] font-mono p-3 outline-none focus:border-[var(--color-active)]"
            />
            <div className="flex justify-end gap-3 mt-2">
              <button onClick={() => { setIsLoginModalOpen(false); setLoginError(""); setPasscode(""); }} className="px-4 py-2 text-[var(--color-muted)] text-sm hover:text-white">Cancel</button>
              <button onClick={handleLoginSubmit} className="px-4 py-2 bg-[var(--color-active)] text-black font-semibold text-sm">Authorize</button>
            </div>
          </div>
        </div>
      )}

      {/* Left Sidebar: Zones & Cameras */}
      <div className="w-64 shrink-0 border-r border-[var(--color-hair)] bg-[var(--color-panel)] flex flex-col">
        <div className="p-3 border-b border-[var(--color-hair)] uppercase tracking-wider text-[10px] font-semibold text-[var(--color-muted)]">
          Cameras & Zones
        </div>
        <div className="p-4 flex-1 text-sm overflow-y-auto space-y-3">
          {CAMERAS.map((cam) => (
            <div
              key={cam.id}
              onClick={() => setSelectedCamera(cam.id)}
              className={`cursor-pointer p-3 border ${selectedCamera === cam.id ? "bg-[var(--color-void)] border-[var(--color-active)]" : "bg-[var(--color-panel)] border-[var(--color-hair)] hover:border-[var(--color-muted)]"}`}
            >
              <div className="text-[var(--color-primary)] mb-1">▶ {cam.id.toUpperCase().replace("_", "-")}</div>
              <div className="text-[var(--color-muted)] text-xs mb-1">{cam.label}</div>
              {selectedCamera === cam.id && cam.id === "cam_05" && (
                <div className="pl-4 mt-2">
                  <div className="text-[var(--color-muted)] text-xs mb-1">Zone A (Restricted)</div>
                  <div className="text-[var(--color-muted)] text-xs mb-2">Zone B (Warning)</div>
                  <div className="text-[var(--color-active)] text-xs hover:underline">+ Propose Fence Edit</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Center Workspace: Operator Command Center */}
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
                // Special handling for Module 4 (cam_04) to use behavioral videos
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
          <div className="absolute top-0 left-0 right-0 p-2 z-[400] bg-black/60 font-mono text-xs text-[var(--color-muted)] border-b border-[var(--color-hair)] backdrop-blur-sm flex items-center gap-2">
            <span>WORKSPACE //</span>
            <select
              value={selectedCamera}
              onChange={(e) => setSelectedCamera(e.target.value)}
              className="bg-transparent text-[var(--color-active)] border-none outline-none cursor-pointer font-bold hover:text-white transition-colors"
            >
              {CAMERAS.map(cam => (
                <option key={cam.id} value={cam.id} className="bg-[var(--color-void)] text-[var(--color-primary)]">
                  {cam.id.toUpperCase().replace("_", "-")} ({cam.label})
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-h-0 relative mt-8 overflow-hidden">
            {selectedCamera === "cam_01" ? (
              <HumanDetectionFeed />
            ) : selectedCamera === "cam_02" ? (
              <VehicleDetectionFeed />
            ) : selectedCamera === "cam_03" ? (
              <ANPRFeed />
            ) : selectedCamera === "cam_04" ? (
              <BehavioralAnalysis cameraId={selectedCamera} />
            ) : selectedCamera === "cam_05" ? (
              <GeofenceEditor cameraId={selectedCamera} currentUser={"operator_2"} />
            ) : (
              <div className="flex h-full items-center justify-center font-mono text-sm text-[var(--color-muted)]">
                {selectedCamera.toUpperCase().replace("_", "-")} MODULE FEED ACTIVE
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Right Sidebar: Global Alert Rail */}
      <AlertRail
        alertCards={alertCards}
        headerExtra={
          <button
            onClick={() => setIsLoginModalOpen(true)}
            className="bg-[var(--color-void)] border border-[var(--color-hair)] text-[var(--color-active)] font-mono text-xs px-2 py-1 hover:bg-[var(--color-active)] hover:text-black transition-colors"
          >
            COMMANDER LOGIN
          </button>
        }
      />
    </div>
  );
}
