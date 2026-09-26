"""
Automated 7-Part Smoke Test Suite for ANPR Service.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.anpr_service.config import settings
from services.anpr_service.models.events import ANPREvent, BBox, IntrusionEvent, VehicleTrack
from services.anpr_service.pipeline.ocr import UNREADABLE, PlateOCR
from services.anpr_service.services.registry import RegistryClient
from services.anpr_service.services.storage import SnapshotStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("smoke_test")


def test_1_config() -> None:
    logger.info("[Test 1/7] Testing Settings configuration loading...")
    assert settings.model_version == "yolov8n-easyocr-v1"
    assert settings.plate_detector_conf_threshold == 0.4
    assert settings.ocr_conf_threshold == 0.6
    logger.info(" -> Test 1 PASSED: Config settings loaded correctly.")


def test_2_event_models() -> None:
    logger.info("[Test 2/7] Testing Pydantic v2 Event Schemas...")
    bbox = BBox(x=10, y=20, w=100, h=50)
    assert bbox.x == 10 and bbox.w == 100

    now = datetime.now(timezone.utc)
    v_track = VehicleTrack(
        track_id="v_001",
        bbox=bbox,
        vehicle_class="car",
        camera_id="CAM-01",
        timestamp=now,
        confidence=0.95,
        model_version="yolo26-nano-v1",
    )
    assert v_track.track_id == "v_001"

    anpr_evt = ANPREvent(
        track_id="v_001",
        plate_text="DL-04-AB-1234",
        confidence=0.88,
        registered_status="registered",
        camera_id="CAM-01",
        timestamp=now,
        model_version=settings.model_version,
    )
    assert anpr_evt.registered_status == "registered"
    logger.info(" -> Test 2 PASSED: Event models validated.")


def test_3_registry_client() -> None:
    logger.info("[Test 3/7] Testing RegistryClient lookup logic...")
    client = RegistryClient(
        api_url="http://localhost:8000/api/v1/check",
        timeout_sec=2.0,
        mock_enabled=True,
        mock_plates=["DL-04-AB-1234", "MH-12-CD-5678"],
    )

    assert client.check("DL-04-AB-1234") == "registered"
    assert client.check("dl-04-ab-1234") == "registered"
    assert client.check("KA-01-XX-9999") == "unregistered"
    assert client.check(UNREADABLE) == "unknown"
    logger.info(" -> Test 3 PASSED: Registry lookup logic working as expected.")


def test_4_snapshot_storage() -> None:
    logger.info("[Test 4/7] Testing SnapshotStorage local file generation...")
    test_dir = Path("snapshots_test")
    storage = SnapshotStorage(
        mock_enabled=True,
        local_path=str(test_dir),
        endpoint="localhost:9000",
        bucket="test-bucket",
        access_key="admin",
        secret_key="admin",
    )

    synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(synthetic_frame, "TEST SNAPSHOT", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    snapshot_url = storage.upload(track_id="v_test_99", frame=synthetic_frame)
    assert snapshot_url is not None
    assert Path(snapshot_url).exists()
    logger.info(" -> Test 4 PASSED: Snapshot stored successfully at %s", snapshot_url)


def test_5_ocr_pipeline() -> None:
    logger.info("[Test 5/7] Testing PlateOCR unreadable & fallback handling...")
    blank_crop = np.zeros((50, 150, 3), dtype=np.uint8)
    
    # Empty / blank crop should return UNREADABLE
    ocr = PlateOCR(
        conf_threshold=0.6,
        languages=["en"],
        model_storage_path=settings.ocr_model_storage_path,
        user_network_path=settings.ocr_user_network_path,
    )
    text, conf = ocr.read(blank_crop)
    assert text == UNREADABLE
    logger.info(" -> Test 5 PASSED: Blank/Low-confidence crop correctly handled as UNREADABLE.")


def test_6_full_pipeline() -> None:
    logger.info("[Test 6/7] Testing ANPRService.process_vehicle_crop pipeline...")
    from services.anpr_service.main import ANPRService

    service = ANPRService()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (300, 200), (255, 255, 255), -1)

    event = service.process_vehicle_crop(
        track_id="v_smoke_100",
        camera_id="CAM-01",
        frame=frame,
    )
    assert event.track_id == "v_smoke_100"
    assert event.registered_status in ("registered", "unregistered", "unknown")
    logger.info(" -> Test 6 PASSED: ANPRService full processing pipeline executed cleanly.")


def test_7_intrusion_handling() -> None:
    logger.info("[Test 7/7] Testing Intrusion correlation & snapshot triggering...")
    from services.anpr_service.main import ANPRService

    service = ANPRService()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # 1. Process a track manually and force status to unregistered in cache
    evt = service.process_vehicle_crop(track_id="v_unreg_999", camera_id="CAM-01", frame=frame)
    # Mock cache to unregistered status for testing intrusion capture
    object.__setattr__(evt, "registered_status", "unregistered")
    service._track_cache["v_unreg_999"] = evt

    # 2. Trigger intrusion event
    now = datetime.now(timezone.utc)
    intrusion = IntrusionEvent(
        track_id="v_unreg_999",
        zone_id="ZONE-ALPHA",
        severity="high",
        camera_id="CAM-01",
        timestamp=now,
    )

    url = service.handle_intrusion(intrusion, frame)
    assert url is not None
    logger.info(" -> Test 7 PASSED: Snapshot captured for unregistered intrusion: %s", url)


def main() -> None:
    logger.info("==================================================")
    logger.info("   RUNNING ANPR SERVICE SMOKE TEST SUITE          ")
    logger.info("==================================================")
    
    test_1_config()
    test_2_event_models()
    test_3_registry_client()
    test_4_snapshot_storage()
    test_5_ocr_pipeline()
    test_6_full_pipeline()
    test_7_intrusion_handling()

    logger.info("==================================================")
    logger.info("   ALL 7 ANPR SMOKE TESTS PASSED SUCCESSFULLY!    ")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
