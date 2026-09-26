"""
ANPR Service — Main Orchestrator & Demo CLI
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from .config import settings
from .models.events import ANPREvent, IntrusionEvent
from .pipeline.detector import PlateDetector
from .pipeline.ocr import PlateOCR, UNREADABLE
from .services.event_logger import EventLogger
from .services.registry import RegistryClient
from .services.storage import SnapshotStorage

logger = logging.getLogger(__name__)


class ANPRService:
    def __init__(self) -> None:
        logger.info("ANPRService: initialising pipeline components...")

        self._detector = PlateDetector(
            model_path=settings.plate_detector_model_path,
            conf_threshold=settings.plate_detector_conf_threshold,
        )
        self._ocr = PlateOCR(
            conf_threshold=settings.ocr_conf_threshold,
            languages=settings.ocr_language,
            model_storage_path=settings.ocr_model_storage_path,
            user_network_path=settings.ocr_user_network_path,
        )
        self._registry = RegistryClient(
            api_url=settings.registry_api_url,
            timeout_sec=settings.registry_timeout_sec,
            mock_enabled=settings.registry_mock_enabled,
            mock_plates=settings.registry_mock_plates,
        )
        self._storage = SnapshotStorage(
            mock_enabled=settings.storage_mock_enabled,
            local_path=settings.storage_local_path,
            endpoint=settings.minio_endpoint,
            bucket=settings.minio_bucket,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
        )
        self._event_logger = EventLogger(log_path=settings.events_log_path)

        self._track_cache: dict[str, ANPREvent] = {}
        logger.info("ANPRService: ready.")

    def process_vehicle_crop(
        self,
        track_id: str,
        camera_id: str,
        frame: np.ndarray,
    ) -> ANPREvent:
        timestamp = datetime.now(timezone.utc)
        if frame is None or frame.size == 0:
            plate_text = UNREADABLE
            ocr_conf = 0.0
            reg_status = "unknown"
        else:
            bbox = self._detector.detect(frame)

            if bbox is None:
                plate_text = UNREADABLE
                ocr_conf = 0.0
                reg_status = "unknown"
            else:
                plate_crop = frame[
                    bbox.y : bbox.y + bbox.h,
                    bbox.x : bbox.x + bbox.w,
                ]
                plate_text, ocr_conf = self._ocr.read(plate_crop)
                reg_status = self._registry.check(plate_text)

        event = ANPREvent(
            track_id=track_id,
            plate_text=plate_text,
            confidence=ocr_conf,
            registered_status=reg_status,
            camera_id=camera_id,
            timestamp=timestamp,
            model_version=settings.model_version,
        )

        logger.info(
            "anpr_event | track=%s plate=%s conf=%.4f status=%s cam=%s model=%s",
            event.track_id,
            event.plate_text,
            event.confidence,
            event.registered_status,
            event.camera_id,
            event.model_version,
        )

        self._track_cache[track_id] = event
        self._event_logger.log_event(event)
        return event

    def handle_intrusion(
        self,
        intrusion: IntrusionEvent,
        frame: np.ndarray,
    ) -> str | None:
        cached = self._track_cache.get(intrusion.track_id)

        if cached is None:
            logger.warning(
                "handle_intrusion: no ANPR result cached for track=%s — skipping snapshot",
                intrusion.track_id,
            )
            return None

        if cached.registered_status != "unregistered":
            logger.debug(
                "handle_intrusion: track=%s status='%s' — snapshot not triggered",
                intrusion.track_id,
                cached.registered_status,
            )
            return None

        logger.info(
            "handle_intrusion: unregistered vehicle track=%s crossed zone=%s — capturing snapshot",
            intrusion.track_id,
            intrusion.zone_id,
        )

        try:
            url = self._storage.upload(track_id=intrusion.track_id, frame=frame)
            logger.info("Snapshot stored: %s", url)
            return url
        except Exception as exc:
            logger.error(
                "handle_intrusion: snapshot upload failed for track=%s: %s",
                intrusion.track_id,
                exc,
            )
            return None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="ANPR Service Demo CLI")
    parser.add_argument("--image", type=str, help="Path to input vehicle image")
    parser.add_argument("--webcam", action="store_true", help="Run live ANPR stream on webcam")
    parser.add_argument("--webcam-index", type=int, default=0, help="Webcam device index (default 0)")
    parser.add_argument("--track-id", type=str, default="v_demo_01", help="Track ID")
    parser.add_argument("--camera-id", type=str, default="CAM-01", help="Camera ID")
    args = parser.parse_args()

    if args.webcam:
        logger.info("Opening webcam index %d...", args.webcam_index)
        cap = cv2.VideoCapture(args.webcam_index)
        if not cap.isOpened():
            logger.error("Failed to open webcam index %d", args.webcam_index)
            sys.exit(1)

        service = ANPRService()
        frame_count = 0
        logger.info("Webcam active! Press 'q' in the video window to quit.")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            # Run ANPR processing every 10 frames for smooth performance
            if frame_count % 10 == 0:
                track_id = f"v_cam_{frame_count}"
                event = service.process_vehicle_crop(
                    track_id=track_id,
                    camera_id=args.camera_id,
                    frame=frame,
                )
                if event.plate_text != UNREADABLE:
                    color = (0, 255, 0) if event.registered_status == "registered" else (0, 0, 255)
                    cv2.putText(
                        frame,
                        f"PLATE: {event.plate_text} ({event.registered_status})",
                        (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        color,
                        2,
                    )

            cv2.imshow("ANPR Live Webcam Feed - Press 'q' to exit", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        logger.info("Webcam feed closed.")
        sys.exit(0)

    if not args.image:
        logger.info("No input specified. Use --webcam to run on webcam or --image <path> to test image.")
        sys.exit(0)

    image_path = Path(args.image)
    if not image_path.exists():
        logger.error("Image file not found: %s", image_path)
        sys.exit(1)

    frame = cv2.imread(str(image_path))
    if frame is None:
        logger.error("Failed to decode image: %s", image_path)
        sys.exit(1)

    service = ANPRService()
    event = service.process_vehicle_crop(
        track_id=args.track_id,
        camera_id=args.camera_id,
        frame=frame,
    )
    print("\n=== Result ANPREvent ===")
    print(event.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
