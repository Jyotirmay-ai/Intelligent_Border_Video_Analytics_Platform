import argparse
import cv2
import sqlite3
import os
import datetime
import time
import json
import sys
from pathlib import Path
from ultralytics import YOLO

try:
    import redis
except ImportError:
    redis = None

SRC_DIR = Path(__file__).resolve().parent
MODULE_DIR = SRC_DIR.parent
PROJECT_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(SRC_DIR))
from events import create_vehicle_track_event
from classifier import FineGrainedClassifier
from tracker import VehicleTracker


ALERT_CHANNEL = "ibvap_alerts"
ALERT_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ALERT_THROTTLE_SECONDS = 12.0

def publish_vehicle_alert(alert_bus, camera_id, track_id, vehicle_class, confidence, last_alerts):
    """Send a low-volume CAM-02 event compatible with the dashboard alert rail."""
    if alert_bus is None:
        return
    alert_key = (track_id, vehicle_class)
    now = time.time()
    if now - last_alerts.get(alert_key, 0.0) < ALERT_THROTTLE_SECONDS:
        return
    

    alert = {
        "module": "module_2",
        "event_type": "Vehicle Detected",
        "zone_id": "ZONE_CAM_02",
        "severity": "info",
        "camera_id": camera_id,
        "timestamp": now,
        "object_id": track_id,
        "evidence": f"{vehicle_class.replace('_', ' ').title()} detected ({confidence:.0%} confidence)",
    }
    try:
        alert_bus.publish(ALERT_CHANNEL, json.dumps(alert))
        last_alerts[alert_key] = now
        print(f"[ALERT PUBLISHED] {alert['event_type']}: {track_id} ({vehicle_class})")
    except Exception as error:
        print(f"[ALERT WARNING] Could not publish CAM-02 alert: {error}")

def main():
    parser = argparse.ArgumentParser(description="Vehicle Detection & Classification")
    parser.add_argument("--video", type=str, default="data/sample_videos/3.1.mp4", help="Path to the input video file")
    parser.add_argument("--camera-id", type=str, default="cam_02", help="Camera ID")
    parser.add_argument("--preview", action="store_true", help="Open a local OpenCV preview window")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Custom YOLO weights. Defaults to the trained specialised model when available.",
    )
    parser.add_argument(
        "--min-truck-confidence",
        type=float,
        default=0.60,
        help="Minimum confidence before a truck is shown or saved (default: 0.60).",
    )
    parser.add_argument(
        "--min-other-vehicle-confidence",
        type=float,
        default=0.30,
        help="Minimum confidence before non-truck vehicles are shown or saved (default: 0.30).",
    )
    args = parser.parse_args()

    print("Starting Vehicle Detection & Classification Module...")

    # Redis is optional for local frame processing, but needed to surface CAM-02
    # detections in the shared dashboard alert rail.
    alert_bus = None
    if redis is None:
        print("[ALERT WARNING] redis package is not installed; CAM-02 alert publishing is disabled.")
    else:
        try:
            alert_bus = redis.from_url(ALERT_REDIS_URL)
            alert_bus.ping()
            print(f"Connected to Redis alert bus at {ALERT_REDIS_URL}")
        except Exception as error:
            print(f"[ALERT WARNING] Redis unavailable; CAM-02 alert publishing is disabled: {error}")
            alert_bus = None
    last_alerts = {}
    
    # --- Database & Storage Setup ---
    # Create a folder to store the image files
    crops_dir = MODULE_DIR / "crops"
    os.makedirs(crops_dir, exist_ok=True)
    
    # Connect to a local SQLite database (it will be created if it doesn't exist)
    conn = sqlite3.connect(str(MODULE_DIR / "vehicles.db"))
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_records (
            track_id TEXT PRIMARY KEY,
            vehicle_class TEXT,
            arrival_time TEXT,
            image_path TEXT,
            confidence REAL
        )
    ''')
    # Upgrade databases created before confidence was stored.
    cursor.execute("PRAGMA table_info(vehicle_records)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "confidence" not in existing_columns:
        cursor.execute("ALTER TABLE vehicle_records ADD COLUMN confidence REAL")
    conn.commit()
    conn.commit()
    
    # A set to remember which vehicles we have already saved
    seen_track_ids = set()
    cursor.execute("SELECT track_id FROM vehicle_records")
    for row in cursor.fetchall():
        seen_track_ids.add(row[0])
    # --------------------------------
    
    # 1. Initialize our components
    classifier = FineGrainedClassifier()
    tracker = VehicleTracker() # We'll use this just for formatting the 'v_' prefix now!
    
    # 2. Load YOLO. Prefer the specialised model after fine-tuning, but keep the
    # original COCO model usable until custom weights have been produced.
    print("Loading YOLO model...")
    project_root = PROJECT_ROOT
    trained_model_path = project_root / "runs" / "traffic_specialized" / "yolov8n" / "weights" / "best.pt"
    if args.model:
        requested_model = Path(args.model)
        model_path = requested_model if requested_model.is_absolute() else Path.cwd() / requested_model
    elif trained_model_path.exists():
        model_path = trained_model_path
    else:
        model_path = project_root / "yolov8n.pt"

    if not model_path.exists():
        print(f"Error: YOLO weights were not found at {model_path.resolve()}.")
        return

    model = YOLO(str(model_path))
    using_specialised_model = "two_wheeler" in {str(name) for name in model.names.values()}
    yolo_model_version = model_path.stem
    print(f"Using YOLO weights: {model_path.resolve()}")
    camera_id = args.camera_id.upper()
    source_config_path = PROJECT_ROOT / "data" / "runtime" / "cam_02_source.json"
    dashboard_frame_path = project_root / "dashboard" / "public" / "processed" / f"{args.camera_id.lower()}.jpg"
    dashboard_frame_temp_path = dashboard_frame_path.with_name(f"{args.camera_id.lower()}_next.jpg")
    dashboard_frame_path.parent.mkdir(parents=True, exist_ok=True)
    last_dashboard_write = 0.0
    last_source_check = 0.0
    
    # 3. Open a video stream
    # Provide the path to your video file via the --video argument.
    video_path = Path(args.video)
    if not video_path.is_absolute():
        video_path = project_root / video_path
    if not os.path.exists(video_path):
        video_path = MODULE_DIR / args.video

    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error: Could not open video source ({video_path}). Please ensure the file exists and is a valid video format.")
        return

    print(f"Starting {camera_id} video stream. Dashboard output: {dashboard_frame_path}")
    
    while True:
        if time.perf_counter() - last_source_check >= 0.5:
            try:
                if source_config_path.exists():
                    selected = json.loads(source_config_path.read_text(encoding="utf-8")).get("source")
                    selected_path = Path(selected) if Path(selected).is_absolute() else PROJECT_ROOT / selected
                    if selected and str(selected_path.resolve()).lower() != str(Path(video_path).resolve()).lower():
                        cap.release()
                        video_path = selected_path
                        cap = cv2.VideoCapture(str(video_path))
                        print(f"Switched {camera_id} source to {video_path}")
            except (OSError, json.JSONDecodeError):
                pass
            last_source_check = time.perf_counter()

        # Read a frame from the webcam/video
        ret, frame = cap.read()
        if not ret:
            cap.release()
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                print(f"Error: Could not restart video source ({video_path}).")
                break
            continue
            
        # 4. Run YOLO with built-in ByteTrack.
        # COCO IDs apply only to the original model. A fine-tuned model uses the
        # 13 specialised class IDs from training/traffic_specialized.yaml, so it
        # must not be filtered with COCO IDs.
        class_filter = None if using_specialised_model else [2, 3, 5, 7]
        tracker_config = Path(__file__).resolve().parent / "traffic_bytetrack.yaml"
        results = model.track(
            frame,
            persist=True,
            tracker=str(tracker_config),
            classes=class_filter,
            verbose=False,
        )
        
        # Use these stable labels instead of the raw single-frame labels when
        # drawing the video output.
        display_detections = []

        # 5. Process the detections if any vehicles were found
        if results[0].boxes.id is not None:
            # Extract bounding boxes, track IDs, class IDs, and confidences from PyTorch tensors
            boxes = results[0].boxes.xywh.cpu().tolist() # xywh format (center x, center y, width, height)
            track_ids = results[0].boxes.id.int().cpu().tolist()
            class_ids = results[0].boxes.cls.int().cpu().tolist()
            confs = results[0].boxes.conf.cpu().tolist()
            
            for box, raw_track_id, cls_id, conf in zip(boxes, track_ids, class_ids, confs):
                x_center, y_center, w, h = box
                
                # Convert center xywh to top-left xywh to match our CONTRACTS.md requirement
                top_x = int(x_center - (w / 2))
                top_y = int(y_center - (h / 2))
                bbox = {"x": max(0, top_x), "y": max(0, top_y), "w": int(w), "h": int(h)}
                
                # Ensure it starts with 'v_'
                formatted_track_id = tracker.format_track_id(raw_track_id)
                
                # Read names from the active model. This works for both the COCO
                # model and the fine-tuned specialised-traffic model.
                raw_class = str(results[0].names.get(cls_id, "unknown"))
                # Keep checking every frame, but display the class that had the
                # strongest confidence at any point in this vehicle's track.
                # A later lower-confidence result can never change that answer.
                base_class, best_confidence, is_new_best = tracker.best_classification(
                    formatted_track_id, raw_class, conf
                )
                minimum_confidence = (
                    args.min_truck_confidence
                    if base_class == "truck"
                    else args.min_other_vehicle_confidence
                )
                # Retain weak boxes for tracking, but only promote a vehicle to
                # the UI/database once it meets its class-specific threshold.
                if best_confidence < minimum_confidence:
                    continue
                
                # Crop vehicle image for detailed classification
                crop = classifier.crop_vehicle(frame, bbox)
                
                # The specialised detector already emits the final label. The old
                # lightweight classifier is only retained for the fallback COCO model.
                if crop is not None and crop.size > 0 and not using_specialised_model:
                    detailed_class, _ = classifier.classify(crop, base_class)
                    vehicle_class = detailed_class.replace(" ", "_") # e.g. "mini_truck"
                else:
                    vehicle_class = base_class
                
                # --- Database Storage Logic ---
                # If we haven't seen this vehicle before, save its 1st cropped picture!
                if formatted_track_id not in seen_track_ids and crop is not None and crop.size > 0:
                    arrival_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    image_path = str(crops_dir / f"{formatted_track_id}_{vehicle_class}_crop.jpg")
                    
                    # 1. Save the cropped vehicle image file to disk
                    cv2.imwrite(image_path, crop)
                    
                    # 2. Save the record to the database
                    cursor.execute('''
                        INSERT OR IGNORE INTO vehicle_records
                        (track_id, vehicle_class, arrival_time, image_path, confidence)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (formatted_track_id, vehicle_class, arrival_time, image_path, best_confidence))
                    conn.commit()
                    
                    # 3. Mark as seen so we don't save it again
                    seen_track_ids.add(formatted_track_id)
                    print(f"[*] SAVED TO DB: First sighting of {formatted_track_id} at {arrival_time}")
                elif is_new_best and formatted_track_id in seen_track_ids:
                    # The vehicle was already saved, but a later frame gave us
                    # a more confident class. Keep the database in sync with
                    # the stable label shown in the video.
                    cursor.execute('''
                        UPDATE vehicle_records
                        SET vehicle_class = ?, confidence = ?
                        WHERE track_id = ?
                    ''', (vehicle_class, best_confidence, formatted_track_id))
                    conn.commit()
                # ------------------------------
                
                # 6. Format the output event exactly as CONTRACTS.md demands
                event_json = create_vehicle_track_event(
                    track_id=formatted_track_id,
                    bbox=bbox,
                    vehicle_class=vehicle_class,
                    camera_id=camera_id,
                    confidence=best_confidence,
                    model_version=yolo_model_version
                )
                
                print(f"[EVENT PUBLISHED] -> {event_json}")
                publish_vehicle_alert(
                    alert_bus,
                    camera_id,
                    formatted_track_id,
                    vehicle_class,
                    best_confidence,
                    last_alerts,
                )
                display_detections.append((bbox, formatted_track_id, vehicle_class, conf))
                
        # 7. Draw only our stable labels. Do not use results[0].plot(): some
        # Ultralytics versions still add confidence text even when labels are
        # disabled, while the requested display must not show confidence.
        annotated_frame = frame.copy()
        for bbox, track_id, vehicle_class, confidence in display_detections:
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
            color = (0, 255, 0)
            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 2)
            label = f"{track_id} {vehicle_class}"
            cv2.putText(
                annotated_frame,
                label,
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )

        if time.perf_counter() - last_dashboard_write >= 0.10:
            try:
                if cv2.imwrite(str(dashboard_frame_temp_path), annotated_frame):
                    try:
                        os.replace(str(dashboard_frame_temp_path), str(dashboard_frame_path))
                    except PermissionError:
                        cv2.imwrite(str(dashboard_frame_path), annotated_frame)
                    last_dashboard_write = time.perf_counter()
            except PermissionError:
                pass
        if args.preview:
            cv2.imshow("Vehicle Detection (Press 'q' to exit)", annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
    # Clean up when done
    cap.release()
    if args.preview:
        cv2.destroyAllWindows()
    conn.close()
    if alert_bus is not None:
        alert_bus.close()

if __name__ == "__main__":
    main()
