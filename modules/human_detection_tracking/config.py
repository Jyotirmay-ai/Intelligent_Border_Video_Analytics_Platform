"""
human-detection-tracking Configuration Module
============================================
All settings are namespaced to prevent collision with other SIH modules.
Update values here or override via CLI arguments (e.g., --cam 1).
This module merges features from:
- face-recognition: ArcFace embedding, enrollment, cosine matching, dataset management
- human-classification: YOLO human detect, RTSP reconnection, HUD dashboard, frame resize
Note: Install dependencies once in the project root:
  pip install -r modules/human_detection_tracking/requirements.txt
"""

# ==========================================
# 1. VIDEO SOURCE CONFIGURATION (merged from human-classification)
# ==========================================
# CAM-01's assigned demonstration footage. Use a webcam index or RTSP URL here
# later when the module is integrated with a physical camera.
VIDEO_SOURCE: int | str = "data/sample_videos/1.1.mp4"
# Runtime handoff written by the dashboard source selector. The module polls this
# small file so CAM-01 can switch its demonstration footage without a restart.
SOURCE_CONFIG_PATH: str = "data/runtime/cam_01_source.json"
SOURCE_CONFIG_CHECK_INTERVAL_SEC: float = 0.5
ALERT_REDIS_URL: str = "redis://localhost:6379"
FACE_ALERT_THROTTLE_SEC: float = 10.0

# ==========================================
# 2. HUMAN DETECTION CONFIGURATION (merged from human-classification)
# ==========================================
# Model choices: 'yolov8n.pt' (lightweight, fastest), 'yolov8s.pt' (balanced)
HUMAN_MODEL_NAME: str = "yolov8n.pt"

# Confidence threshold for human detection (Range: 0.0 to 1.0)
HUMAN_CONF_THRESHOLD: float = 0.50

# Class ID for 'person' in standard COCO dataset is 0
HUMAN_TARGET_CLASS_ID: int = 0

# ==========================================
# 3. FACE RECOGNITION CONFIGURATION (merged from face-recognition)
# ==========================================
# Similarity threshold for face matching using Cosine Similarity
FACE_SIMILARITY_THRESHOLD: float = 0.45

# InsightFace model pack: "buffalo_s" for fast CPU, "buffalo_l" for high precision
FACE_INSIGHTFACE_MODEL_PACK: str = "buffalo_s"

# YuNet face detector ONNX model path (inside this module folder)
FACE_YUNET_MODEL_PATH: str = "models/face_detection_yunet_2026may.onnx"

# Face detection model settings
FACE_YUNET_SCORE_THRESHOLD: float = 0.7
FACE_YUNET_NMS_THRESHOLD: float = 0.3

# ==========================================
# 4. ENROLLMENT CONFIGURATION (merged from face-recognition)
# ==========================================
# Directory containing person subfolders such as dataset/Deeya/
DATASET_PATH: str = "dataset"
# Pickle file database for identity embeddings
EMBEDDINGS_PATH: str = "dataset/embeddings.pkl"
# Number of face crops to capture during live webcam enrollment
WEBcam_SAMPLES_COUNT: int = 8

# ==========================================
# 5. PERFORMANCE & DEVICE SETTINGS (merged from human-classification)
# ==========================================
# Force device selection: 'cpu' or 'cuda'
DEVICE_CHOICE: str = "cpu"

# Optional frame resize width for faster processing (Set to None to disable resizing)
# Resizing large 4K / 1080p RTSP streams significantly improves FPS
FRAME_RESIZE_WIDTH: int | None = 960

# RTSP Reconnection settings
MAX_RECONNECT_ATTEMPTS: int = 5
RECONNECT_DELAY_SEC: float = 2.0

# ==========================================
# 6. VISUAL DISPLAY & HUD SETTINGS (merged from human-classification)
# ==========================================
WINDOW_TITLE: str = "Real-Time Human Detection & Face Tracking"
# This module is normally served through its MJPEG endpoint. Keep this disabled when
# using opencv-python-headless, which cannot open a native desktop window.
ENABLE_LOCAL_PREVIEW: bool = False

# The latest annotated CAM-01 frame is written here for the Next.js dashboard.
# This is a shared-file handoff, not a standalone video-feed server.
DASHBOARD_FRAME_OUTPUT: str = "dashboard/public/processed/cam_01.jpg"
DASHBOARD_FRAME_WRITE_INTERVAL_SEC: float = 0.10
# Bounding box color for humans (BGR format)
HUMAN_BBOX_COLOR: tuple[int, int, int] = (0, 230, 115)
# Bounding box color for faces (BGR format)
FACE_BBOX_COLOR: tuple[int, int, int] = (0, 255, 0)
# Text color for labels
TEXT_COLOR: tuple[int, int, int] = (255, 255, 255)
# Background color for header bar
BG_COLOR: tuple[int, int, int] = (20, 20, 20)
# Height of top dashboard bar in pixels
HEADER_HEIGHT: int = 50

# ==========================================
# 7. PIPELINE SETTINGS
# ==========================================
# Perform full detection + embedding extraction every Nth frame (performance balance)
HUMAN_DETECTION_FRAME_INTERVAL: int = 2
# Face matching is more expensive than person detection. Cache each result between
# runs so the recognized name stays visible while keeping CAM-01 responsive.
FACE_ANALYSIS_FRAME_INTERVAL: int = 6
