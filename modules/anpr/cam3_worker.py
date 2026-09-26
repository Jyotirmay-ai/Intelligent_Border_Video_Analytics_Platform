"""Independent CAM-03 ANPR adapter for the IBVAP dashboard.

This process owns its video source, vehicle tracks, OCR pipeline, local ANPR log,
and failure handling.  Its only integration boundaries are a processed JPEG and
Redis JSON messages, so it can stop or restart without disrupting other modules.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import cv2

try:
    import redis
except ImportError:
    redis = None

MODULE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_ROOT.parent.parent
sys.path.insert(0, str(MODULE_ROOT / "services"))

from anpr_service.main import ANPRService  # noqa: E402
from anpr_service.pipeline.ocr import UNREADABLE  # noqa: E402

LOGGER = logging.getLogger("anpr.cam03")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
RAW_EVENT_CHANNEL = "ibvap_anpr_events"
ALERT_CHANNEL = "ibvap_alerts"
VEHICLE_CLASSES = [2, 3, 5, 7]  # car, motorcycle, bus, truck in COCO


def resolve_source(source: str) -> Path:
    path = Path(source)
    return path if path.is_absolute() else PROJECT_ROOT / path


def publish(bus, channel: str, payload: dict) -> None:
    if bus is None:
        return
    try:
        bus.publish(channel, json.dumps(payload))
    except Exception as error:
        LOGGER.warning("Redis publish failed on %s: %s", channel, error)


def write_dashboard_frame(frame, destination: Path, temporary: Path) -> None:
    try:
        if cv2.imwrite(str(temporary), frame):
            try:
                os.replace(temporary, destination)
            except PermissionError:
                cv2.imwrite(str(destination), frame)
    except PermissionError:
        # A brief browser file lock must never terminate the module.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent IBVAP CAM-03 ANPR worker")
    parser.add_argument("--video", default="data/sample_videos/2.2.mp4", help="Local MP4 or absolute path")
    parser.add_argument("--camera-id", default="CAM_03")
    parser.add_argument("--sample-interval", type=float, default=3.0, help="Minimum seconds between OCR attempts per track")
    parser.add_argument("--max-frames", type=int, default=0, help="Test mode: stop after this many frames")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    source_config = PROJECT_ROOT / "data" / "runtime" / "cam_03_source.json"
    source = resolve_source(args.video)
    output = PROJECT_ROOT / "dashboard" / "public" / "processed" / "cam_03.jpg"
    temporary = output.with_name("cam_03_next.jpg")
    output.parent.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        raise SystemExit(f"CAM-03 source was not found: {source}")

    bus = None
    if redis is not None:
        try:
            bus = redis.from_url(REDIS_URL)
            bus.ping()
            LOGGER.info("Connected to Redis event bus")
        except Exception as error:
            LOGGER.warning("Redis unavailable; CAM-03 will continue with local outputs only: %s", error)
            bus = None
    else:
        LOGGER.warning("redis package unavailable; CAM-03 will continue with local outputs only")

    try:
        from ultralytics import YOLO
        detector = YOLO(str(PROJECT_ROOT / "yolov8n.pt"))
        service = ANPRService()
    except Exception as error:
        if bus is not None:
            bus.close()
        raise SystemExit(f"CAM-03 initialization failed without affecting other modules: {error}")

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        if bus is not None:
            bus.close()
        raise SystemExit(f"Unable to open CAM-03 source: {source}")

    LOGGER.info("CAM-03 ANPR worker started with source: %s", source)
    last_source_check = 0.0
    last_ocr_attempt: dict[str, float] = {}
    labels: dict[str, str] = {}
    processed = 0

    try:
        while True:
            now = time.monotonic()
            if now - last_source_check >= 0.5:
                try:
                    if source_config.exists():
                        saved = json.loads(source_config.read_text(encoding="utf-8")).get("source")
                        candidate = resolve_source(saved) if isinstance(saved, str) else source
                        if candidate.exists() and candidate.resolve() != source.resolve():
                            cap.release()
                            source = candidate
                            cap = cv2.VideoCapture(str(source))
                            labels.clear()
                            last_ocr_attempt.clear()
                            LOGGER.info("CAM-03 source switched to %s", source)
                except (OSError, json.JSONDecodeError):
                    pass
                last_source_check = now

            ok, frame = cap.read()
            if not ok:
                cap.release()
                cap = cv2.VideoCapture(str(source))
                if not cap.isOpened():
                    LOGGER.error("Unable to restart CAM-03 source: %s", source)
                    break
                continue

            processed += 1
            annotated = frame.copy()
            try:
                results = detector.track(frame, persist=True, classes=VEHICLE_CLASSES, verbose=False)
                boxes = results[0].boxes
                if boxes.id is not None:
                    xyxy = boxes.xyxy.cpu().tolist()
                    track_ids = boxes.id.int().cpu().tolist()
                    confidences = boxes.conf.cpu().tolist()
                    for coords, raw_track, vehicle_confidence in zip(xyxy, track_ids, confidences):
                        x1, y1, x2, y2 = (int(value) for value in coords)
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                        if x2 <= x1 or y2 <= y1:
                            continue
                        track_id = f"anpr_{raw_track:04d}"
                        crop = frame[y1:y2, x1:x2]

                        if now - last_ocr_attempt.get(track_id, 0.0) >= args.sample_interval:
                            last_ocr_attempt[track_id] = now
                            try:
                                event = service.process_vehicle_crop(track_id, args.camera_id, crop)
                                raw = event.model_dump(mode="json")
                                publish(bus, RAW_EVENT_CHANNEL, raw)
                                if event.plate_text != UNREADABLE:
                                    labels[track_id] = f"{event.plate_text} | {event.registered_status.upper()}"
                                    alert = {
                                        "module": "module_4",
                                        "event_type": "Unregistered Vehicle Plate" if event.registered_status == "unregistered" else "License Plate Detected",
                                        "zone_id": "ZONE_CAM_03",
                                        "severity": "warning" if event.registered_status == "unregistered" else "info",
                                        "camera_id": args.camera_id,
                                        "timestamp": time.time(),
                                        "object_id": track_id,
                                        "evidence": f"Plate {event.plate_text} ({event.confidence:.0%} OCR confidence, {event.registered_status})",
                                    }
                                    publish(bus, ALERT_CHANNEL, alert)
                            except Exception as error:
                                LOGGER.warning("ANPR processing failed for %s; continuing: %s", track_id, error)

                        label = labels.get(track_id, "ANPR scanning")
                        color = (0, 255, 255) if "UNREGISTERED" in label else (0, 255, 0)
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(annotated, label, (x1, max(22, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
            except Exception as error:
                LOGGER.warning("Frame inference failed; continuing: %s", error)

            write_dashboard_frame(annotated, output, temporary)
            if args.max_frames and processed >= args.max_frames:
                break
    finally:
        cap.release()
        if bus is not None:
            bus.close()


if __name__ == "__main__":
    main()
