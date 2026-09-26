"""
Video Testing & Visual Overlay Runner for Suspicious Activity Detection Engine (Module 6).
Features Permanent Target Lock: Keeps track boxes active indefinitely even when person stands completely still.
"""

import sys
import math
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Ensure rules_alert_engine is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

import cv2
import numpy as np

from src.engine_service import EngineService
from src.models import (
    HumanTrackEvent,
    VehicleTrackEvent,
    BoundingBox,
    NightModeFlag,
    IntrusionEvent,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run Suspicious Activity Detection on Video or Webcam")
    parser.add_argument("--video", type=str, default="0", help="Path to video file (.mp4/.avi) or '0' for live webcam")
    parser.add_argument("--night", action="store_true", help="Enable Night Mode (tighter dwell-time thresholds)")
    parser.add_argument("--dwell", type=float, default=None, help="Override dwell threshold in seconds (e.g. --dwell 3)")
    parser.add_argument("--output", type=str, default="", help="Path to save annotated output video")
    parser.add_argument("--zone", type=str, default="restricted", choices=["restricted", "warning", "outer_watch"])
    return parser.parse_args()


class PermanentTargetTracker:
    """
    Maintains target lock indefinitely across stationary postures, occlusions, and pauses.
    Only deletes a track if it physically moves out of the camera view (frame borders).
    """
    def __init__(self, frame_w=1920, frame_h=1080, max_dist_px=140):
        self.next_id = 1
        self.tracks = {}  # tid -> {"box": [x1, y1, x2, y2], "stationary_frames": 0, "cls": 0, "conf": 0.9}
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.max_dist_px = max_dist_px

    def compute_centroid(self, box):
        return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)

    def compute_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        return interArea / float(boxAArea + boxBArea - interArea + 1e-6)

    def suppress_duplicate_detections(self, raw_boxes):
        if not raw_boxes:
            return []

        cleaned = []
        for det in raw_boxes:
            box = det[:4]
            is_dup = False
            for c in cleaned:
                c_box = c[:4]
                iou = self.compute_iou(box, c_box)
                cx1, cy1 = self.compute_centroid(box)
                cx2, cy2 = self.compute_centroid(c_box)
                dist = math.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2)
                
                if iou > 0.20 or dist < 70:
                    is_dup = True
                    break
            if not is_dup:
                cleaned.append(det)
        return cleaned

    def update(self, raw_detections):
        detections = self.suppress_duplicate_detections(raw_detections)
        matched_tracks = set()
        matched_dets = set()
        results = []

        # 1. Match detections to existing tracks
        for tid, tdata in self.tracks.items():
            t_box = tdata["box"]
            tc_x, tc_y = self.compute_centroid(t_box)
            
            best_dist = float("inf")
            best_d_idx = -1

            for d_idx, det in enumerate(detections):
                if d_idx in matched_dets:
                    continue
                d_box = det[:4]
                dc_x, dc_y = self.compute_centroid(d_box)
                dist = math.sqrt((tc_x - dc_x) ** 2 + (tc_y - dc_y) ** 2)
                iou = self.compute_iou(t_box, d_box)

                if dist < best_dist and (dist < self.max_dist_px or iou > 0.10):
                    best_dist = dist
                    best_d_idx = d_idx

            if best_d_idx != -1:
                det = detections[best_d_idx]
                # Smooth box position
                smoothed = [
                    int(0.6 * det[0] + 0.4 * t_box[0]),
                    int(0.6 * det[1] + 0.4 * t_box[1]),
                    int(0.6 * det[2] + 0.4 * t_box[2]),
                    int(0.6 * det[3] + 0.4 * t_box[3]),
                ]
                self.tracks[tid]["box"] = smoothed
                self.tracks[tid]["stationary_frames"] = 0
                self.tracks[tid]["cls"] = det[4]
                self.tracks[tid]["conf"] = det[5]
                matched_tracks.add(tid)
                matched_dets.add(best_d_idx)
            else:
                # Target is stationary / still in scene -> keep locked at last position!
                self.tracks[tid]["stationary_frames"] += 1

        # 2. Register new detections if not matched
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_dets:
                # Check distance from all existing tracks before creating new ID
                dc_x, dc_y = self.compute_centroid(det[:4])
                is_near_existing = any(
                    math.sqrt((dc_x - self.compute_centroid(tdata["box"])[0])**2 + (dc_y - self.compute_centroid(tdata["box"])[1])**2) < 80
                    for tdata in self.tracks.values()
                )
                if not is_near_existing:
                    tid = self.next_id
                    self.next_id += 1
                    self.tracks[tid] = {
                        "box": [int(det[0]), int(det[1]), int(det[2]), int(det[3])],
                        "stationary_frames": 0,
                        "cls": det[4],
                        "conf": det[5]
                    }
                    matched_tracks.add(tid)

        # 3. Only remove a track if it physically touched the screen border (exited camera)
        exited_tids = []
        for tid, tdata in list(self.tracks.items()):
            b = tdata["box"]
            near_border = (b[0] < 10 or b[1] < 10 or b[2] > (self.frame_w - 10) or b[3] > (self.frame_h - 10))
            if near_border and tdata["stationary_frames"] > 60:
                exited_tids.append(tid)

        for tid in exited_tids:
            del self.tracks[tid]

        # 4. Return all locked active tracks
        for tid, tdata in self.tracks.items():
            b = tdata["box"]
            results.append((tid, b[0], b[1], b[2], b[3], tdata["cls"], tdata["conf"]))

        return results


def draw_hud(frame, track_states, fps, night_mode, zone_id, effective_dwell_thresh):
    """Draws a live telemetry HUD box in the top-right corner."""
    h, w = frame.shape[:2]
    hud_width = 390
    hud_x = max(10, w - hud_width - 15)
    hud_y = 15
    box_height = 42 + max(1, len(track_states)) * 28
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (hud_x - 5, hud_y - 5), (w - 15, hud_y + box_height), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.rectangle(frame, (hud_x - 5, hud_y - 5), (w - 15, hud_y + box_height), (80, 80, 80), 1)

    mode_str = "[NIGHT MODE]" if night_mode else "[DAY MODE]"
    cv2.putText(frame, f"TELEMETRY | ZONE: {zone_id.upper()} | {mode_str}", (hud_x + 5, hud_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 2)
    
    y_cursor = hud_y + 45
    if not track_states:
        cv2.putText(frame, "No targets detected in camera view", (hud_x + 5, y_cursor),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)
    else:
        for tid, (dwell_s, speed_mps, dist_m) in track_states.items():
            dwell_color = (0, 0, 255) if dwell_s >= effective_dwell_thresh else (0, 255, 0)
            text = f"ID:{tid} | Dwell: {dwell_s:.1f}s / {effective_dwell_thresh:.0f}s | Spd: {speed_mps:.1f}m/s"
            cv2.putText(frame, text, (hud_x + 5, y_cursor),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, dwell_color, 1)
            y_cursor += 25

    return frame


def draw_alert_banner(frame, alerts):
    """Draws prominent Alert Rail cards at the top-left of the video frame."""
    if not alerts:
        return frame

    y_offset = 40
    for alert in alerts:
        color_map = {
            "critical": (0, 0, 255),    # Bright Red
            "high": (0, 140, 255),      # Orange/Yellow
            "medium": (255, 255, 0),    # Cyan
            "low": (0, 255, 0),         # Green
        }
        color = color_map.get(alert.severity, (0, 255, 255))

        banner_text = f"ALERT [{alert.severity.upper()}] {alert.rule_id.upper()}: {alert.explanation}"
        (w, h), _ = cv2.getTextSize(banner_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        
        cv2.rectangle(frame, (15, y_offset - 26), (35 + w, y_offset + 12), (0, 0, 0), -1)
        cv2.rectangle(frame, (15, y_offset - 26), (35 + w, y_offset + 12), color, 3)
        cv2.putText(frame, banner_text, (22, y_offset - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

        y_offset += 48

    return frame


def run_video_pipeline(video_source: str, night_mode: bool = False, output_path: str = "", zone_id: str = "restricted", dwell_override: float = None):
    print("=" * 80)
    print("  IBVAP - SUSPICIOUS ACTIVITY DETECTION ENGINE (PERMANENT LOCK)")
    print("=" * 80)

    # 1. Resolve Video File Path
    if video_source == "0":
        source = 0
        print("[INFO] Using Live Webcam (Camera 0)...")
    else:
        video_path = Path(video_source)
        if not video_path.is_absolute():
            if not video_path.exists():
                candidate = Path.cwd() / video_source
                if candidate.exists():
                    video_path = candidate
        
        if not video_path.exists():
            print(f"❌ Error: Video file '{video_source}' not found!")
            return
        
        source = str(video_path)
        print(f"[INFO] Loading Video: {source}")

    # 2. Open Video Stream
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ Error: Could not open video '{source}'")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"[INFO] Resolution: {width}x{height} | FPS: {fps:.1f} | Total Frames: {total_frames}")

    # 3. Setup Large Resizable Window
    window_name = "IBVAP - Suspicious Activity Detection Engine"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    # 4. Initialize Engine & Config
    config_path = Path(__file__).parent / "config" / "default_zone_config.json"
    engine = EngineService(config_path)

    if dwell_override is not None:
        engine.config.dwell_time_threshold_s = dwell_override
        engine.feature_extractor.config.dwell_time_threshold_s = dwell_override
        engine.rule_evaluator.config.dwell_time_threshold_s = dwell_override
        print(f"[CONFIG OVERRIDE] Dwell Time Threshold set to: {dwell_override}s")
    
    start_sim_time = datetime.now()
    engine.process_night_mode_flag(NightModeFlag(
        camera_id="CAM-01",
        night_mode_active=night_mode,
        timestamp=start_sim_time
    ))

    effective_dwell_thresh = engine.config.dwell_time_threshold_s * (engine.config.night_multiplier if night_mode else 1.0)
    print(f"[INFO] Zone: '{zone_id.upper()}' | Night Mode: {'ON' if night_mode else 'OFF'} | Alert Threshold: {effective_dwell_thresh:.1f}s")

    # 5. Output Video Writer
    out_writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        print(f"[INFO] Saving output to: {output_path}")

    # 6. Initialize Permanent Target Tracker
    tracker = PermanentTargetTracker(frame_w=width, frame_h=height)

    # 7. Load YOLO or OpenCV Fallback
    use_yolo = False
    try:
        from ultralytics import YOLO
        print("[INFO] Loading YOLOv8 tracking model...")
        model = YOLO("yolov8n.pt")
        use_yolo = True
    except (ImportError, Exception) as e:
        print(f"[INFO] Using OpenCV detector: {e}")
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)

    print("\n▶️ Video is playing! Press 'q' on video window or CTRL+C in terminal to exit.\n")

    frame_idx = 0
    delay_ms = max(1, int(1000 / fps))
    persistent_alerts = []  # Keep active alert visible once triggered

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("\n[INFO] Video playback complete.")
                break

            current_time = start_sim_time + timedelta(seconds=(frame_idx / fps))
            frame_idx += 1
            active_alerts = []
            telemetry_tracks = {}
            raw_detections = []

            # --- Detection Phase ---
            if use_yolo:
                results = model(frame, conf=0.18, classes=[0, 2, 5, 7], verbose=False)
                if results and results[0].boxes and len(results[0].boxes) > 0:
                    b_xyxy = results[0].boxes.xyxy.cpu().numpy()
                    b_cls = results[0].boxes.cls.int().cpu().numpy()
                    b_conf = results[0].boxes.conf.cpu().numpy()
                    for box, cls_id, conf in zip(b_xyxy, b_cls, b_conf):
                        raw_detections.append((box[0], box[1], box[2], box[3], cls_id, conf))
            else:
                boxes, _ = hog.detectMultiScale(frame, winStride=(8, 8), scale=1.05)
                for (x, y, w, h) in boxes:
                    raw_detections.append((x, y, x + w, y + h, 0, 0.85))
                
                if len(raw_detections) == 0:
                    fg_mask = bg_subtractor.apply(frame)
                    _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for c in contours:
                        if cv2.contourArea(c) > 2000:
                            bx, by, bw, bh = cv2.boundingRect(c)
                            raw_detections.append((bx, by, bx + bw, by + bh, 0, 0.75))

            # --- Permanent Tracking Phase ---
            tracked_objects = tracker.update(raw_detections)

            # --- Behavioral Analytics Phase ---
            for (track_id, x1, y1, x2, y2, cls_id, conf) in tracked_objects:
                w, h = x2 - x1, y2 - y1
                tid_str = f"track_{track_id}"

                fence_y = height * 0.85
                dist_to_fence = max(2.0, round((fence_y - y2) / 10.0, 1))

                if cls_id == 0:  # Person
                    engine.process_intrusion_event(IntrusionEvent(
                        track_id=tid_str,
                        zone_id=zone_id,
                        severity="high" if zone_id == "restricted" else "medium",
                        camera_id="CAM-01",
                        timestamp=current_time
                    ))
                    alerts = engine.process_human_track(HumanTrackEvent(
                        track_id=tid_str,
                        bbox=BoundingBox(x=float(x1), y=float(y1), w=float(w), h=float(h)),
                        camera_id="CAM-01",
                        timestamp=current_time,
                        confidence=float(conf),
                        distance_to_fence_m=dist_to_fence
                    ))
                    active_alerts.extend(alerts)

                    # Get telemetry
                    track_state = engine.state_mgr.get_or_create_track(tid_str)
                    feat = engine.feature_extractor.extract_features(track_state, engine.state_mgr, current_time, night_mode)
                    telemetry_tracks[track_id] = (feat.dwell_time_s, feat.speed_mps, dist_to_fence)

                    # Determine if alert is active (or was triggered)
                    is_threat = len(alerts) > 0 or (feat.dwell_time_s >= effective_dwell_thresh)
                    if is_threat:
                        box_color = (0, 0, 255)  # Bright Red
                        tag_text = f"THREAT (ID:{track_id}) | Dwell: {feat.dwell_time_s:.1f}s"
                    else:
                        box_color = (0, 255, 0)  # Solid Green
                        tag_text = f"ID:{track_id} Person ({feat.dwell_time_s:.1f}s)"

                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), box_color, 2)
                    cv2.putText(frame, tag_text, (int(x1), max(22, int(y1) - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 2)
                else:  # Vehicle
                    alerts = engine.process_vehicle_track(VehicleTrackEvent(
                        track_id=tid_str,
                        bbox=BoundingBox(x=float(x1), y=float(y1), w=float(w), h=float(h)),
                        vehicle_class="vehicle",
                        camera_id="CAM-01",
                        timestamp=current_time,
                        confidence=float(conf),
                        distance_to_fence_m=dist_to_fence
                    ))
                    active_alerts.extend(alerts)

                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 200, 0), 2)
                    cv2.putText(frame, f"ID:{track_id} Vehicle", (int(x1), max(22, int(y1) - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 2)

            # Keep alerts persistent once triggered
            if active_alerts:
                persistent_alerts = active_alerts

            # Print active alerts in console
            for a in active_alerts:
                print(f"🚨 [{a.severity.upper()}] {a.rule_id}: {a.explanation} (Track: {a.track_id})")



            # Draw Live Telemetry HUD (Top Right)
            frame = draw_hud(frame, telemetry_tracks, fps, night_mode, zone_id, effective_dwell_thresh)

            # Overlay Persistent Alert Rail Banners (Top Left)
            frame = draw_alert_banner(frame, persistent_alerts if len(telemetry_tracks) > 0 else [])

            if out_writer:
                out_writer.write(frame)

            cv2.imshow(window_name, frame)
            if cv2.waitKey(delay_ms) & 0xFF == ord('q'):
                print("[INFO] User requested stop.")
                break

    except KeyboardInterrupt:
        print("[INFO] Interrupted.")

    finally:
        cap.release()
        if out_writer:
            out_writer.release()
        cv2.destroyAllWindows()
        print("=" * 80)
        print("  Processing complete.")
        print("=" * 80)


if __name__ == "__main__":
    args = parse_args()
    run_video_pipeline(
        video_source=args.video,
        night_mode=args.night,
        output_path=args.output,
        zone_id=args.zone,
        dwell_override=args.dwell,
    )
