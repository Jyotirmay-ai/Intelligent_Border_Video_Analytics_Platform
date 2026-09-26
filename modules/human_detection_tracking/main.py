"""
human-detection-tracking - Main Execution Script
================================================
Isolated module merging features from:
  - face-recognition: ArcFace embedding, cosine similarity matching, enrollment, dataset management
  - human-classification: YOLO human detection, RTSP reconnection, HUD dashboard, frame resize, EMA FPS
"""

import sys
import os
import time
import logging
import argparse
import cv2
import numpy as np
import pickle
import json
try:
    import redis
except ImportError:
    redis = None

# Ensure the module is importable regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import namespaced config
from human_detection_tracking.config import (
    VIDEO_SOURCE, HUMAN_MODEL_NAME, HUMAN_CONF_THRESHOLD, HUMAN_TARGET_CLASS_ID,
    SOURCE_CONFIG_PATH, SOURCE_CONFIG_CHECK_INTERVAL_SEC,
    ALERT_REDIS_URL, FACE_ALERT_THROTTLE_SEC,
    DEVICE_CHOICE, FRAME_RESIZE_WIDTH, MAX_RECONNECT_ATTEMPTS, RECONNECT_DELAY_SEC,
    WINDOW_TITLE, HUMAN_BBOX_COLOR, BG_COLOR, HEADER_HEIGHT,
    ENABLE_LOCAL_PREVIEW,
    DASHBOARD_FRAME_OUTPUT, DASHBOARD_FRAME_WRITE_INTERVAL_SEC,
    FACE_SIMILARITY_THRESHOLD, FACE_INSIGHTFACE_MODEL_PACK, FACE_YUNET_MODEL_PATH,
    FACE_YUNET_SCORE_THRESHOLD, FACE_YUNET_NMS_THRESHOLD,
    DATASET_PATH, EMBEDDINGS_PATH, WEBcam_SAMPLES_COUNT, HUMAN_DETECTION_FRAME_INTERVAL,
    FACE_ANALYSIS_FRAME_INTERVAL,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(MODULE_DIR))

def project_path(path):
    """Resolve module configuration paths from the project root."""
    return path if os.path.isabs(path) else os.path.join(PROJECT_DIR, path)

def source_identity(source):
    """Use one comparable identity for relative and absolute local video paths."""
    if isinstance(source, str) and not source.lower().startswith(("rtsp://", "http://", "https://")):
        return os.path.normcase(os.path.abspath(project_path(source)))
    return source

def publish_face_alert(alert_bus, label, timestamp, last_alerts):
    if alert_bus is None:
        return
    known = label != "Unknown"
    person_name = label.split(" (")[0] if known else "Unknown person"
    now = time.time()
    if now - last_alerts.get(person_name, 0) < FACE_ALERT_THROTTLE_SEC:
        return
    alert = {
        "module": "module_1",
        "event_type": "Known Person Spotted" if known else "Unknown Person Lurking",
        "zone_id": "ZONE_CAM_01",
        "severity": "info" if known else "warning",
        "camera_id": "CAM_01",
        "timestamp": timestamp,
        "object_id": person_name,
        "evidence": f"Face analysis matched {person_name}" if known else "Face detected with no enrolled match",
    }
    try:
        alert_bus.publish("ibvap_alerts", json.dumps(alert))
        last_alerts[person_name] = now
    except Exception as error:
        logging.debug("Could not publish CAM-01 face alert: %s", error)

def write_dashboard_frame(frame, target_path, temporary_path):
    """Publish a frame without allowing Windows file locks to stop the worker."""
    if not cv2.imwrite(temporary_path, frame):
        return False
    try:
        os.replace(temporary_path, target_path)
        return True
    except PermissionError:
        # Next.js may briefly hold the public image open. Direct overwrite is
        # compatible with that reader and avoids killing the processing loop.
        try:
            return bool(cv2.imwrite(target_path, frame))
        except PermissionError:
            logging.debug("Dashboard frame is temporarily locked; skipping one update")
            return False

def cosine_similarity(emb1, emb2):
    if emb1 is None or emb2 is None: return -1.0
    v1, v2 = np.array(emb1, dtype=np.float64), np.array(emb2, dtype=np.float64)
    norm = np.linalg.norm(v1) * np.linalg.norm(v2)
    return float(np.dot(v1, v2) / norm) if norm > 0 else -1.0

def load_embeddings_db(path=EMBEDDINGS_PATH):
    resolved_path = project_path(path)
    if not os.path.exists(resolved_path):
        logging.warning(f"Embeddings DB not found at '{resolved_path}'. Detection-only mode.")
        return {}
    try:
        with open(resolved_path, 'rb') as f:
            db = pickle.load(f)
        identities = db.get("identities", {})
        logging.info("Loaded %d enrolled identity/identities.", len(identities))
        return identities
    except Exception as e:
        logging.error(f"Failed to load embeddings DB: {e}")
        return {}

def init_human_detector():
    try:
        from ultralytics import YOLO
        model = YOLO(HUMAN_MODEL_NAME)
        device = DEVICE_CHOICE.lower()
        if device == "cuda" and not cv2.cuda.getCudaEnabledDeviceCount():
            device = "cpu"
        model.to(device)
        return model
    except Exception as e:
        logging.error(f"YOLO Init Error: {e}")
        sys.exit(1)

def init_face_detector():
    try:
        # Prefer a model packaged with this isolated module, but also support the
        # shared project model location used by the current workspace.
        candidates = [
            os.path.join(MODULE_DIR, FACE_YUNET_MODEL_PATH),
            os.path.join(PROJECT_DIR, "models", os.path.basename(FACE_YUNET_MODEL_PATH)),
        ]
        model_path = next((path for path in candidates if os.path.isfile(path)), None)
        if model_path is None:
            logging.warning("YuNet model was not found. Running in human-only mode.")
            return None
        detector = cv2.FaceDetectorYN.create(model_path, "", (320, 320), 
                                           FACE_YUNET_SCORE_THRESHOLD, FACE_YUNET_NMS_THRESHOLD)
        logging.info(f"YuNet face detector initialized: {model_path}")
        return detector
    except Exception as e:
        logging.warning(f"YuNet face detector init warning: {e}. Running human-only mode.")
        return None

def init_insightface_embedder():
    try:
        from insightface.app import FaceAnalysis
        app_if = FaceAnalysis(name=FACE_INSIGHTFACE_MODEL_PACK)
        app_if.prepare(ctx_id=-1, det_size=(640, 640))
        return app_if
    except Exception as e:
        logging.warning(f"InsightFace Init Warning: {e}")
        return None

def create_video_capture(source):
    cap = cv2.VideoCapture(source)
    if isinstance(source, str) and source.startswith("rtsp"):
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap

def load_dashboard_source(default_source):
    """Read an optional CAM-01 source selected in the dashboard."""
    source_path = project_path(SOURCE_CONFIG_PATH)
    if not os.path.isfile(source_path):
        return default_source
    try:
        with open(source_path, "r", encoding="utf-8") as source_file:
            selected_source = json.load(source_file).get("source")
        return selected_source if isinstance(selected_source, str) and selected_source else default_source
    except (OSError, json.JSONDecodeError) as error:
        logging.warning("Could not read CAM-01 source selection: %s", error)
        return default_source

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cam", type=str, default=None, help="Camera index or video path (e.g. 1 or 'C:/path/to/video.mp4')")
    args = parser.parse_args()
    
    # Determine camera source
    cam_source = VIDEO_SOURCE
    if args.cam is not None:
        cam_source = args.cam
        # If the source is a digit, convert it to an int for OpenCV
        if cam_source.isdigit():
            cam_source = int(cam_source)

    # Resolve local sources once so dashboard polling does not confuse equivalent
    # relative and absolute paths.
    if isinstance(cam_source, str) and not cam_source.lower().startswith(("rtsp://", "http://", "https://")):
        cam_source = project_path(cam_source)

    human_model = init_human_detector()
    face_detector = init_face_detector()
    face_embedder = init_insightface_embedder()
    identities = load_embeddings_db()
    alert_bus = None
    if redis is not None:
        try:
            alert_bus = redis.from_url(ALERT_REDIS_URL)
        except Exception as error:
            logging.warning("CAM-01 alerts disabled: %s", error)

    cap = create_video_capture(cam_source)
    if not cap.isOpened():
        logging.error(f"Unable to open source: {cam_source}")
        sys.exit(1)

    prev_time = time.perf_counter()
    fps_smooth = 0.0
    frame_count = 0
    reconnect_count = 0
    last_source_check = 0.0
    last_dashboard_write = 0.0
    dashboard_frame_path = project_path(DASHBOARD_FRAME_OUTPUT)
    dashboard_frame_temp_path = dashboard_frame_path.replace(".jpg", "_next.jpg")
    os.makedirs(os.path.dirname(dashboard_frame_path), exist_ok=True)
    person_count = 0
    last_human_boxes = []
    last_face_results = []
    last_face_alerts = {}

    try:
        while True:
            if time.perf_counter() - last_source_check >= SOURCE_CONFIG_CHECK_INTERVAL_SEC:
                selected_source = load_dashboard_source(VIDEO_SOURCE)
                selected_capture_source = project_path(selected_source) if isinstance(selected_source, str) else selected_source
                if source_identity(selected_capture_source) != source_identity(cam_source):
                    logging.info("Switching CAM-01 source to %s", selected_capture_source)
                    cap.release()
                    cam_source = selected_capture_source
                    cap = create_video_capture(cam_source)
                    if not cap.isOpened():
                        logging.error("Unable to open selected source: %s", cam_source)
                        cam_source = project_path(VIDEO_SOURCE) if isinstance(VIDEO_SOURCE, str) else VIDEO_SOURCE
                        cap = create_video_capture(cam_source)
                    last_human_boxes = []
                    last_face_results = []
                    person_count = 0
                last_source_check = time.perf_counter()

            ret, frame = cap.read()
            if not ret or frame is None:
                # CAM-01 uses a demonstration MP4: restart it immediately at the end
                # so the dashboard always has a continuous source.
                if isinstance(cam_source, str) and not cam_source.lower().startswith("rtsp"):
                    logging.info("End of video reached. Looping source: %s", cam_source)
                    cap.release()
                    cap = create_video_capture(cam_source)
                    if not cap.isOpened():
                        logging.error("Failed to restart video source: %s", cam_source)
                        time.sleep(RECONNECT_DELAY_SEC)
                        continue
                    continue
                reconnect_count += 1
                if reconnect_count >= MAX_RECONNECT_ATTEMPTS: break
                time.sleep(RECONNECT_DELAY_SEC)
                cap.release()
                cap = create_video_capture(cam_source)
                continue

            reconnect_count = 0
            if FRAME_RESIZE_WIDTH and frame.shape[1] > FRAME_RESIZE_WIDTH:
                aspect = frame.shape[0] / frame.shape[1]
                frame = cv2.resize(frame, (FRAME_RESIZE_WIDTH, int(FRAME_RESIZE_WIDTH * aspect)))

            curr_time = time.perf_counter()
            fps_smooth = (0.1 * (1.0 / (curr_time - prev_time) if curr_time != prev_time else 0)) + (0.9 * fps_smooth)
            prev_time = curr_time
            frame_count += 1

            # Human Detection
            if frame_count % HUMAN_DETECTION_FRAME_INTERVAL == 1:
                results = human_model.predict(source=frame, classes=[HUMAN_TARGET_CLASS_ID], conf=HUMAN_CONF_THRESHOLD, verbose=False)
                last_human_boxes = []
                for result in results:
                    if result.boxes:
                        for box in result.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            last_human_boxes.append((x1, y1, x2, y2, float(box.conf[0])))
                person_count = len(last_human_boxes)
            
            # Face Detection & Matching
            if face_detector and frame_count % FACE_ANALYSIS_FRAME_INTERVAL == 1:
                last_face_results = []
                det_frame = cv2.resize(frame, (320, 320))
                face_detector.setInputSize((320, 320))
                _, faces = face_detector.detect(det_frame)
                insight_faces = face_embedder.get(frame) if face_embedder is not None else []
                if faces is not None:
                    for face in faces:
                        if len(face) >= 4:
                            # YuNet returns x, y, width, height in the 320x320
                            # detection image. Convert them back to the source frame.
                            scale_x = frame.shape[1] / 320
                            scale_y = frame.shape[0] / 320
                            x, y, face_w, face_h = face[:4]
                            fx1, fy1 = int(x * scale_x), int(y * scale_y)
                            fx2, fy2 = int((x + face_w) * scale_x), int((y + face_h) * scale_y)
                            # Shrink the box slightly to ensure labels are clear and not overlapping
                            padding = 5
                            fx1 = max(0, fx1 + padding)
                            fy1 = max(0, fy1 + padding)
                            fx2 = min(frame.shape[1], fx2 - padding)
                            fy2 = min(frame.shape[0], fy2 - padding)
                             
                            if fx2 <= fx1 or fy2 <= fy1:
                                 continue
                            label = "Unknown"


                            if face_embedder and insight_faces:
                                try:
                                    # Use InsightFace's embedding from the full frame;
                                    # re-detecting a tiny face crop often loses the face.
                                    face_center = np.array([(fx1 + fx2) / 2, (fy1 + fy2) / 2])
                                    matched_face = min(
                                        insight_faces,
                                        key=lambda candidate: np.linalg.norm(
                                            np.array([(candidate.bbox[0] + candidate.bbox[2]) / 2,
                                                      (candidate.bbox[1] + candidate.bbox[3]) / 2]) - face_center
                                        ),
                                    )
                                    emb = matched_face.embedding
                                    best_name, best_score = "Unknown", -1.0
                                    for name, data in identities.items():
                                        sim = cosine_similarity(emb, data.get("mean_embedding"))
                                        if sim > best_score: best_score, best_name = sim, name
                                    if best_score >= FACE_SIMILARITY_THRESHOLD:
                                        label = f"{best_name} ({best_score:.2f})"
                                except Exception as error:
                                    logging.debug("Face recognition skipped: %s", error)
                            last_face_results.append((fx1, fy1, fx2, fy2, label))
                            publish_face_alert(alert_bus, label, time.time(), last_face_alerts)

            # Redraw cached analysis on every frame. This prevents boxes/names from
            # flickering while expensive inference runs at a lower frequency.
            for fx1, fy1, fx2, fy2, label in last_face_results:
                cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (0, 255, 0), 3)
                cv2.putText(frame, label, (fx1, max(22, fy1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # HUD
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (0, 0), (w, HEADER_HEIGHT), BG_COLOR, -1)
            cv2.putText(frame, f"People: {person_count}", (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)

            # Hand the most recent annotated CAM-01 frame to the dashboard.
            if time.perf_counter() - last_dashboard_write >= DASHBOARD_FRAME_WRITE_INTERVAL_SEC:
                if write_dashboard_frame(frame, dashboard_frame_path, dashboard_frame_temp_path):
                    last_dashboard_write = time.perf_counter()

            # This stays disabled by default because opencv-python-headless cannot
            # open a native desktop window.
            if ENABLE_LOCAL_PREVIEW:
                cv2.imshow(WINDOW_TITLE, frame)
                if cv2.waitKey(1) & 0xFF in [ord('q'), 27]:
                    break

    except Exception as e:
        logging.error(f"Loop Error: {e}", exc_info=True)
    finally:
        cap.release()
        if alert_bus is not None:
            try:
                alert_bus.close()
            except Exception:
                pass
        if ENABLE_LOCAL_PREVIEW:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
