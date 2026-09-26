# Human Detection & Face Tracking Module
**Module Path:** `D:\software Projects\SIH\ibvap-full-project\modules\human-detection-tracking\`

## ⚠️ Isolation Notice
This module is **fully standalone**. None of the other SIH modules (`face-recognition`, `human-classification`, `suspicious-activity-detection`, `virtual-fence-intrusion-detection`) are imported or modified.
- All configuration lives in `config.py` (namespaced variables: `HUMAN_`, `FACE_`).
- Dependencies must be installed **only** in `D:\software Projects\SIH\ibvap-full-project\` using the command below.
- Output (video frame or JSON) can be consumed by the Next.js dashboard for `cam_1` without touching any dashboard source files.

## Installation
Install all required wheels once in the project root:

```powershell
cd D:\software Projects\SIH\ibvap-full-project
pip install -r modules\human-detection-tracking\requirements.txt
```

## Quick Start (CLI)
Run the module's main pipeline using CAM-01's assigned `1.mp4` footage:

```powershell
cd D:\software Projects\SIH\ibvap-full-project
python -m human_detection_tracking.main
# or override the source when needed:
python -m human_detection_tracking.main --cam "data/sample_videos/1.mp4"
```

The `--cam` flag overrides `config.py` `VIDEO_SOURCE`; it accepts a webcam index,
video file path, or RTSP URL.

## Module Structure
```
human-detection-tracking/
│
├── __init__.py          # Makes this folder a Python package
├── config.py            # Namespaced settings (see config.py for details)
├── requirements.txt     # Packages: opencv-headless, ultralytics, insightface, onnx, numpy, tqdm
├── README.md            # This file
└── main.py              # Entry point: human detect -> face crop/embed -> match/enroll -> annotate
│
```

## How It Works (Internal Pipeline)
1. **Video Ingestion:** Reads from `config.py` `VIDEO_SOURCE` (or `--cam 1` CLI arg).
2. **Human Detection:** Loads YOLOv8n (`HUMAN_MODEL_NAME`), detects `person` class (`HUMAN_TARGET_CLASS_ID`) with `HUMAN_CONF_THRESHOLD`.
3. **Face Extraction:** For each detected person, crops the region-of-interest (ROI).
4. **Face Detection & Embedding:** Uses OpenCV YuNet + InsightFace ArcFace to extract a 512D L2-normalized embedding.
5. **Matching:** Compares embedding against `dataset/embeddings.pkl` using Cosine Similarity (`FACE_SIMILARITY_THRESHOLD`).
6. **Annotation:** Draws bounding boxes, identity labels ("Known: Name" or "Unknown"), FPS, and a HUD dashboard.
7. **Enrollment (Optional):** If a face is "Unknown" and the user presses a key, `enroll_from_webcam` logic can save a new identity folder/image (implementation pending in `main.py`).

## Staying Isolated
- Do **not** import from `..face_recognition` or `..human_classification` inside this module.
- Do **not** modify `dashboard/src/app/page.tsx`, `commander/page.tsx`, or any behavioral/virtual-fence files.
- If you need to expose output to the dashboard, use the `main.py` `generate_frame()` return value or the simple JSON API pattern (see `main.py` docstring).
