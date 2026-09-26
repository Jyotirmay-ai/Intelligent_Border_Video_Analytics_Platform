import os
import json
import redis
import time
import cv2
import numpy as np
from ultralytics import YOLO
from collections import deque

# Connect to Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

# --- FINE-TUNED PARAMETERS (Based on PARAMETERS.md) ---
TARGET_CAMERA = "cam_04"
DWELL_TIME_THRESHOLD = 8       # Reduced slightly for demo impact
ALERT_THROTTLE = 45           # Increased to 45s to allow reading alerts
MIN_CONFIDENCE = 0.45         # Increased to reduce false positives
LINE_DEVIATION_THRESHOLD = 0.6 # Path linearity threshold (1.0 = straight line)

# Region of Interest (ROI) - Only trigger alerts if object is in this area
# [x_min, y_min, x_max, y_max] in percentages (0-100)
RESTRICTED_ZONE = [20, 20, 80, 80] 

# Load YOLOv8n model
print("Loading YOLOv8n model for fine-tuned analysis...")
model = YOLO("yolov8n.pt") 

# State tracking
# { object_id: {"first_seen": timestamp, "last_seen": timestamp, "centroid_history": deque} }
track_history = {}

def calculate_distance(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5

def calculate_path_linearity(history):
    """
    Calculates the ratio of straight-line distance to total path distance.
    1.0 = perfectly straight, lower = erratic/circling.
    """
    if len(history) < 5:
        return 1.0
    
    start = history[0]
    end = history[-1]
    straight_dist = calculate_distance(start, end)
    
    total_dist = 0
    for i in range(1, len(history)):
        total_dist += calculate_distance(history[i-1], history[i])
    
    if total_dist == 0: return 1.0
    return straight_dist / total_dist

def is_in_restricted_zone(centroid, frame_w, frame_h):
    x_px, y_px = centroid
    x_pct = (x_px / frame_w) * 100
    y_pct = (y_px / frame_h) * 100
    return RESTRICTED_ZONE[0] <= x_pct <= RESTRICTED_ZONE[2] and RESTRICTED_ZONE[1] <= y_pct <= RESTRICTED_ZONE[3]

def evaluate_behavioral_rules(obj_id, dwell_time, movement_speed, linearity, in_zone, group_size, detected_classes):
    """
    Fine-tuned Composite Rules Implementation
    """
    alerts = []
    
    # 1. COMPOSITE: Reconnaissance (Loitering + Restricted Zone + Erratic Path)
    # FIX: To avoid marking stationary people (homeless/resting) as loitering,
    # we only trigger this if the object has actually moved a minimum distance
    # while dwelling. Purely stationary objects are ignored.
    if in_zone and dwell_time >= DWELL_TIME_THRESHOLD:
        # We only alert if there is some movement activity (erratic or purposeful)
        # A completely stationary person is not "loitering" in a reconnaissance sense.
        if movement_speed > 0.1: 
            severity = "high" if linearity < LINE_DEVIATION_THRESHOLD else "medium"
            event_type = "Suspicious Loitering" if linearity >= LINE_DEVIATION_THRESHOLD else "Reconnaissance Pattern"
            
            alerts.append({
                "rule_id": "reconnaissance-pattern",
                "event_type": event_type,
                "severity": severity,
                "evidence": f"Dwell: {int(dwell_time)}s, Linearity: {linearity:.2f}"
            })
    
    # 2. COMPOSITE: Asset Theft (Person + Animal + Moving)
    if "dog" in detected_classes and movement_speed > 0.5:
        alerts.append({
            "rule_id": "theft-pattern",
            "event_type": "Suspicious Asset Movement",
            "severity": "critical",
            "evidence": "Co-detection of person and animal in motion"
        })

    # 3. COMPOSITE: Group Infiltration (Group Size > 2 + Restricted Zone)
    if in_zone and group_size > 2:
        alerts.append({
            "rule_id": "coordinated-movement",
            "event_type": "Group Infiltration",
            "severity": "high",
            "evidence": f"Group of {group_size} persons detected in restricted zone"
        })

    # 4. Kinematic Evasion (High Speed)
    if movement_speed > 3.0: 
        alerts.append({
            "rule_id": "evasion-pattern",
            "event_type": "Erratic Movement",
            "severity": "medium",
            "evidence": f"High speed: {movement_speed:.2f} px/frame"
        })
        
    return alerts

def run_behavioral_engine():
    print(f"Fine-Tuned SAD Engine Started for {TARGET_CAMERA}...")
    
    video_path = "data/sample_videos/4.1.mp4"
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video.")
        return
        
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        # Run YOLOv8n inference
        results = model.track(frame, persist=True, classes=[0, 16], conf=MIN_CONFIDENCE, verbose=False)
        
        detected_this_frame = []
        current_person_count = 0
        
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xywh.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            cls = results[0].boxes.cls.int().cpu().tolist()
            
            current_time = time.time()
            
            for box, track_id, class_id in zip(boxes, track_ids, cls):
                class_name = "person" if class_id == 0 else "dog"
                detected_this_frame.append(class_name)
                if class_name == "person":
                    current_person_count += 1
                
                obj_id = f"OBJ-{track_id}"
                x, y, w, h = box
                centroid = (x, y)
                
                if obj_id not in track_history:
                    track_history[obj_id] = {
                        "first_seen": current_time,
                        "last_seen": current_time,
                        "centroid_history": deque(maxlen=30)
                    }
                
                # Update history
                hist = track_history[obj_id]
                hist["last_seen"] = current_time
                hist["centroid_history"].append(centroid)
                
                # Calculate Metrics
                speed = 0
                if len(hist["centroid_history"]) > 1:
                    p1 = hist["centroid_history"][-2]
                    p2 = hist["centroid_history"][-1]
                    speed = calculate_distance(p1, p2)
                
                linearity = calculate_path_linearity(list(hist["centroid_history"]))
                dwell_time = current_time - hist["first_seen"]
                in_zone = is_in_restricted_zone(centroid, frame_w, frame_h)
                
                # Evaluate Composite Rules
                found_alerts = evaluate_behavioral_rules(
                    obj_id, dwell_time, speed, linearity, in_zone, current_person_count, detected_this_frame
                )
                
                for alert_data in found_alerts:
                    full_alert = {
                        "module": "module_4",
                        "event_type": alert_data["event_type"],
                        "zone_id": f"ZONE_{TARGET_CAMERA.upper()}",
                        "severity": alert_data["severity"],
                        "camera_id": TARGET_CAMERA.upper(),
                        "timestamp": current_time,
                        "object_id": obj_id,
                        "evidence": alert_data["evidence"]
                    }
                    r.publish("ibvap_alerts", json.dumps(full_alert))
                    print(f"🚨 {alert_data['event_type']} detected for {obj_id}!")

        frame_count += 1
        if frame_count % 100 == 0:
            print(f"Processed {frame_count} frames...")

    cap.release()

if __name__ == "__main__":
    try:
        run_behavioral_engine()
    except KeyboardInterrupt:
        print("Engine stopped.")
