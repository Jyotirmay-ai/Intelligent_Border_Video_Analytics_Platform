"""
Centralised configuration for the ANPR service.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


MODULE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Plate Detector (Stage 1)
    # Use the shared project model through an absolute path so this isolated
    # module works from any working directory.
    plate_detector_model_path: str = str(PROJECT_ROOT / "yolov8n.pt")
    plate_detector_conf_threshold: float = Field(default=0.4, ge=0.0, le=1.0)

    # OCR (Stage 2)
    ocr_conf_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    ocr_language: list[str] = Field(default=["en"])
    # Keep EasyOCR weights and user networks inside this isolated module rather
    # than allowing EasyOCR to write to the user's home directory.
    ocr_model_storage_path: str = str(MODULE_ROOT / "models" / "easyocr")
    ocr_user_network_path: str = str(MODULE_ROOT / "models" / "easyocr" / "user_network")

    # Registry
    registry_mock_enabled: bool = Field(default=True)
    registry_mock_plates: list[str] = Field(default=["DL-04-AB-1234", "MH-12-CD-5678"])
    registry_api_url: str = "http://localhost:8000/api/v1/vehicles/check"
    registry_timeout_sec: float = Field(default=2.0, gt=0.0)

    # Storage
    storage_mock_enabled: bool = Field(default=True)
    storage_local_path: str = Field(default=str(MODULE_ROOT / "output_storage" / "snapshots"))
    events_log_path: str = Field(default=str(MODULE_ROOT / "output_storage" / "anpr_events_log.json"))
    minio_endpoint: str = "localhost:9000"
    minio_bucket: str = "anpr-snapshots"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"

    # Event Bus Topics
    bus_vehicle_track_topic: str = "vehicle_track"
    bus_intrusion_topic: str = "intrusion_event"
    bus_anpr_topic: str = "anpr_event"

    # Service Identity
    model_version: str = "yolov8n-easyocr-v1"
    camera_id: str = "CAM-01"
    log_level: str = "INFO"


settings = Settings()
