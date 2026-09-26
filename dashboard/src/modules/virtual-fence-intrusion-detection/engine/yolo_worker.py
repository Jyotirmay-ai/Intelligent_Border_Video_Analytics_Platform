import cv2
import time
import json
import redis
import os
import argparse
import threading
from shapely.geometry import Point, Polygon
from ultralytics import YOLO

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

active_fences = {}
last_alert_time = 0

def load_fences():
    fences = r.get("ibvap:fences")
    if fences:
        data = json.loads(fences)
        loaded = {}
        for cam_id, config in data.items():
            pts = [(pt[0], pt[1]) for pt in config["polygon"]]
            if len(pts) > 2:
                loaded["ZONE_" + cam_id.upper()] = {
                    "camera_id": cam_id,
                    "severity": config.get("severity", "critical"),
                    "polygon": Polygon(pts)
                }
        return loaded
    return {}

def config_listener():
    global active_fences
    pubsub = r.pubsub()
    pubsub.subscribe(["ibvap_config_hotreload"])
    for message in pubsub.listen():
        if message["type"] == "message":
            print("[YOLO Fence Engine] Received hot-reload config! Updating in-memory fences.")
            active_fences = load_fences()

def evaluate_intrusion(camera_id, x_percent, y_percent, label):
    global last_alert_time
    pt = Point(x_percent, y_percent)

    if time.time() - last_alert_time < 3:
        return

    for zone_id, fence in active_fences.items():
        if fence["camera_id"] == camera_id:
            poly = fence["polygon"]
            
            is_inside = poly.contains(pt)
            # Distance to the boundary (in percentage space). 5% is a reasonable "near" threshold.
            is_near = not is_inside and poly.exterior.distance(pt) < 5.0
            
            if is_inside or is_near:
                last_alert_time = time.time()
                
                event_type = "Intrusion Detected" if is_inside else "Proximity Warning"
                severity = fence["severity"] if is_inside else "warning"
                location_text = "inside" if is_inside else "near"
                
                alert = {
                    "module": "module_5",
                    "event_type": event_type,
                    "zone_id": zone_id,
                    "severity": severity,
                    "camera_id": camera_id.upper(),
                    "timestamp": time.time(),
                    "object_id": f"OBJ-{str(time.time()).replace('.', '')[-6:]}",
                    "evidence": f"AI Detected {label} at ({x_percent:.1f}%, {y_percent:.1f}%) - {location_text} zone."
                }
                print(f">>> {event_type.upper()}! {label} {location_text} {zone_id} <<<")
                r.publish("ibvap_alerts", json.dumps(alert))



def run_yolo_fence_worker(video_path: str, camera_id: str, fps_limit: int = 15):
    global active_fences
    active_fences = load_fences()
    
    threading.Thread(target=config_listener, daemon=True).start()

    print(f"Loading YOLO11 (yolov8n.pt) for {camera_id}...")
    model = YOLO('yolov8n.pt') 

    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return

    print(f"Starting Live YOLO Geofence Pipeline for {camera_id} on {video_path}")
    cap = cv2.VideoCapture(video_path)
    
    frame_delay = 1.0 / fps_limit
    
    try:
        while cap.isOpened():
            start_time = time.time()
            ret, frame = cap.read()
            
            if not ret:
                print("End of video stream. Looping...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
                
            height, width, _ = frame.shape
            
            # COCO Classes: 0: person, 15-23: various animals (cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe)
            target_classes = [0, 15, 16, 17, 18, 19, 20, 21, 22, 23]
            results = model.predict(frame, classes=target_classes, verbose=False)
            
            for r_res in results:
                boxes = r_res.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cls_id = int(box.cls[0].item())
                    
                    label = "Person" if cls_id == 0 else "Animal"
                    
                    # Compute bottom-center of the bounding box
                    cx = (x1 + x2) / 2
                    cy = y2 
                    
                    x_percent = (cx / width) * 100
                    y_percent = (cy / height) * 100
                    
                    evaluate_intrusion(camera_id, x_percent, y_percent, label)

            elapsed = time.time() - start_time
            if elapsed < frame_delay:
                time.sleep(frame_delay - elapsed)
    except KeyboardInterrupt:
        print("YOLO Pipeline stopped.")
    finally:
        cap.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live YOLO Geofence Worker")
    parser.add_argument("--video", type=str, required=True, help="Path to mp4 file")
    parser.add_argument("--camera-id", type=str, default="cam_05", help="Camera ID")
    parser.add_argument("--fps", type=int, default=15, help="FPS limit")
    
    args = parser.parse_args()
    run_yolo_fence_worker(args.video, args.camera_id, args.fps)
