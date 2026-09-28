# IBVAP — Intelligent Border Video Analytics Platform

IBVAP is a local, software-first border-security command prototype. It turns CCTV footage into operator-facing video analytics, alerts, camera-zone controls, and command views. The current build uses local MP4 files as simulated live camera feeds; it is designed so RTSP/IP-camera inputs can replace them later.

> **Prototype scope:** IBVAP supports human/face analytics on CAM-01, vehicle analytics on CAM-02, ANPR on CAM-03, suspicious-activity alerts on CAM-04, and virtual-fence intrusion alerts on CAM-05. The dashboard, two-section alert rail, and video-source controls connect these demonstrable flows.

## Current implementation status

| Capability | Current status | Notes |
| --- | --- | --- |
| Command dashboard | Implemented | Next.js operator and commander views, sector map, camera grid, alert rail, and workspace panels. |
| Human detection and face matching | Implemented on CAM-01 | YOLO human detection, YuNet face detection, InsightFace matching, known/unknown face alerts, selectable MP4 sources. |
| Vehicle detection and classification | Implemented on CAM-02 | YOLO vehicle classes and ByteTrack tracking, selectable MP4 sources, annotated dashboard feed, vehicle crops/local SQLite data, and Redis vehicle alerts. |
| Suspicious-activity analytics | Implemented on CAM-04 | Worker evaluates demo behavioural events and publishes alerts through Redis. A more structured rules engine is also included. |
| Virtual-fence intrusion | Implemented on CAM-05 | Fence editing and proposal flow in the dashboard; Redis-configured worker publishes intrusion alerts. Fence capability is deliberately restricted to CAM-05. |
| Alerting and live event display | Implemented for connected workers | Redis Pub/Sub feeds the dashboard alert rail through Server-Sent Events. |
| FastAPI service | Present, optional in current demo | FastAPI can forward Redis alerts over WebSockets, but the default launcher does not start it because the dashboard directly consumes Redis for its alert stream. |
| PostgreSQL/PostGIS | Docker service defined | The compose stack defines PostGIS and Redis. Current dashboard fence/proposal state and event flow primarily use Redis; full durable database-backed audit/event storage is future integration work. |
| ANPR / OCR | Implemented on CAM-03 | Independent YOLO vehicle tracking, EasyOCR plate reading, mock registry checks, local ANPR event log/snapshots, processed dashboard feed, and Redis alerts. |
| Night-time analytics | Not implemented | Planned, not part of the current demo. |

## Camera and module mapping

| Camera | Module | Default startup source | Dashboard behaviour |
| --- | --- | --- | --- |
| CAM-01 | Human detection and face recognition | `data/sample_videos/1.1.mp4` | Shows face-only boxes and known/unknown labels. Source can be changed in the workspace. |
| CAM-02 | Vehicle detection and classification | `data/sample_videos/2.1.mp4` | Shows vehicle detections/tracks. Source can be changed in the workspace. |
| CAM-03 | Automatic Number Plate Recognition | `data/sample_videos/2.2.mp4` | Selectable source, annotated ANPR feed, local event logging, and plate-status alerts. |
| CAM-04 | Suspicious-activity analytics | Worker-configured demo footage | Behavioural alerts appear in the alert rail. |
| CAM-05 | Virtual-fence intrusion detection | `data/sample_videos/5.mp4` | Fence editor and commander proposal/approval flow. |
| CAM-06 | Reserved / placeholder | None | No active module currently assigned. |

The current selectable source files are kept in `data/sample_videos/`. The active CAM-01 and CAM-02 choices are stored in:

- `data/runtime/cam_01_source.json`
- `data/runtime/cam_02_source.json`

## Architecture at a glance

```text
MP4 CCTV simulator / future RTSP cameras
              |
              v
   Python + OpenCV video processing
              |
              +--> CAM-01: YOLO + YuNet + InsightFace
              +--> CAM-02: YOLO + ByteTrack
              +--> CAM-03: YOLO + EasyOCR ANPR
              +--> CAM-04: behavioural worker / rules engine
              +--> CAM-05: virtual-fence worker
              |
              v
       Redis Pub/Sub (ibvap_alerts)
              |
              v
 Next.js dashboard SSE → shared AlertRail component
   ┌─────────────────────────────────────┐
   │ ALERTS (critical / warning cards)   │
   ├─────────────────────────────────────┤
   │ ACTIVITY FEED (collapsed per-cam)   │
   └─────────────────────────────────────┘

PostgreSQL/PostGIS is available through Docker for future durable spatial and audit data.
```

## Repository layout

```text
ibvap-full-project/
├── dashboard/                         # Next.js + React + Tailwind command dashboard
│   └── src/
│       ├── app/                       # Operator (/) and Commander (/commander) pages
│       │   └── api/alerts/            # SSE route handler consuming Redis
│       └── components/
│           └── AlertRail.tsx          # Shared two-section alert rail + useAlertCards hook
├── backend/                           # FastAPI alert WebSocket service and video simulator
├── modules/
│   ├── human_detection_tracking/      # CAM-01 human and face matching pipeline
│   ├── vehicle-detection-classification/ # CAM-02 vehicle pipeline
│   ├── anpr/                          # CAM-03 isolated ANPR pipeline
│   ├── suspicious-activity-detection/ # CAM-04 worker and rules engine
│   ├── virtual-fence-intrusion-detection/ # CAM-05 fence workers/UI assets
│   └── _shared/CONTRACTS.md           # Cross-module event schema contracts
├── data/
│   ├── sample_videos/                 # Local MP4 camera simulations
│   └── runtime/                       # Selected CAM-01/CAM-02 source configuration
├── dataset/                           # Enrolled face identities and embeddings
├── models/                            # Shared model files, including YuNet ONNX
├── docs/                              # Architecture, PRD, workflows, parameters
├── docker-compose.yml                 # Redis and PostgreSQL/PostGIS services
├── start_system.ps1                   # Clears Node/Python processes, then launches demo workers
└── start_all.ps1                      # Opens the dashboard and all 5 camera workers
```

## Technology stack

| Layer | Technologies used now |
| --- | --- |
| Frontend | Next.js, React, Tailwind CSS, Leaflet / React Leaflet |
| Dashboard integration | Next.js route handlers, Server-Sent Events, processed JPEG polling |
| Backend | Python, FastAPI, Redis client libraries |
| Video and AI | OpenCV, Ultralytics YOLO, ByteTrack, YuNet, InsightFace |
| Real-time events | Redis Pub/Sub (`ibvap_alerts`) |
| Data services | Redis; PostgreSQL + PostGIS defined in Docker Compose |
| Simulation | Local MP4 CCTV footage processed as looping/continuous camera sources |

## Prerequisites

- Windows with PowerShell
- Python 3.11 and the project virtual environment at `.venv`
- Node.js and npm
- Docker Desktop, if you want Redis/PostGIS through the included compose stack
- Required model files in the project root/model directories (for example `yolov8n.pt` and `models/face_detection_yunet_2026may.onnx`)

## Start the demo

### 1. Start Redis and PostGIS

From the project root:

```powershell
docker compose up -d
```

Redis on port `6379` is required for alert publishing, alert streaming, and virtual-fence configuration. PostGIS is exposed on port `5432`.

### 2. Launch the dashboard and enabled workers

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start_system.ps1
```

`start_system.ps1` force-stops existing `node` and `python` processes before calling `start_all.ps1`. Do not use it if unrelated Node/Python applications are running on the same machine.

The launcher opens separate PowerShell windows for the dashboard and the CAM-01, CAM-02, CAM-03, CAM-04, and CAM-05 processes. The dashboard normally runs at:

```text
http://localhost:3000          # Operator view
http://localhost:3000/commander # Commander view (passcode: ALPHA-7)
```

### Optional: start FastAPI alert WebSocket service

This is not required for the default dashboard alert rail, but is available for other WebSocket clients:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000
```

## Face identity enrollment

Add face images to a named folder under `dataset/`, then regenerate embeddings:

```text
dataset/
├── PersonNameA/
│   ├── image1.jpg
│   └── image2.jpg
└── PersonNameB/
    └── image1.jpg
```

```powershell
.\.venv\Scripts\Activate.ps1
python modules\human_detection_tracking\enroll.py
```

The enrollment process updates `dataset/embeddings.pkl`. Restart the CAM-01 worker after enrollment so it loads the new identities.

## Runtime outputs and event flow

- Each active camera worker writes its processed frame to `dashboard/public/processed/cam_XX.jpg`.
- The dashboard refreshes these processed images in the active-sector/workspace views.
- CAM-01 publishes **Known Person Spotted** and **Unknown Person Lurking** events to `ibvap_alerts`.
- CAM-02 publishes throttled **Vehicle Detected** events to `ibvap_alerts`.
- CAM-03 publishes raw `anpr_event` records to `ibvap_anpr_events` and readable-plate alerts to `ibvap_alerts`.
- CAM-04 publishes suspicious-activity events to `ibvap_alerts`.
- CAM-05 publishes virtual-fence intrusion events to `ibvap_alerts`.
- The dashboard reads the `ibvap_alerts` Redis channel through `/api/alerts` (SSE) and renders events in the **shared AlertRail component**.

### Alert rail design

The alert rail uses a **two-section layout** to separate signal from noise:

| Section | Content | Behavior |
| --- | --- | --- |
| **ALERTS** (top) | `critical` and `warning` severity events (intrusions, suspicious activity, unregistered vehicles) | Full individual cards with 3px severity-colored left border, sorted newest-first |
| **ACTIVITY FEED** (bottom) | `info`-level detections (humans, vehicles, plates) | Collapsed into one summary row per camera (e.g. "CAM-02 · 14 vehicles detected"), expandable to show the last 5 individual detections |

Both sections auto-decay cards after 30 seconds of inactivity. The AlertRail component (`dashboard/src/components/AlertRail.tsx`) and its `useAlertCards()` hook are shared between the Operator and Commander pages.

## Module notes and limitations

- Modules are intentionally developed as **isolated pipelines**. Dashboard integration occurs through processed-frame files, small source-selection APIs, and Redis messages rather than direct imports between modules. If a module fails, only its camera feed stops; the dashboard and remaining workers continue operating.
- CAM-01 is a combined human/face pipeline. Face labels are drawn around faces, not whole human bodies.
- CAM-02 publishes throttled `Vehicle Detected` events to the shared alert rail for qualified tracked vehicles.
- CAM-03 runs an independent YOLO vehicle tracker with EasyOCR plate reading and mock registry status checks.
- CAM-05 uses a simulated worker in the default startup path. A separate YOLO-based fence worker is included but is not the default launched worker.
- The proposal/approval experience is a prototype workflow. It is not a production authentication, authorization, or tamper-proof audit system.
- This repository is a local demonstration system. It has no hardened access control, encrypted biometric storage, retention policies, model governance, or production-scale camera orchestration.

## Verification

The current dashboard code passes ESLint with no errors. There are four non-blocking unused-variable warnings in the alert and dashboard pages. The Python entry points for the enabled workers compile successfully in the project virtual environment.

## Documentation




