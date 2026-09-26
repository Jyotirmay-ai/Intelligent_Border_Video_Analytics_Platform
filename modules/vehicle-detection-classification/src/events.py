import json
from datetime import datetime

def create_vehicle_track_event(track_id: str, bbox: dict, vehicle_class: str, camera_id: str, confidence: float, model_version: str) -> str:
    """
    Creates a JSON string matching the vehicle_track contract.
    CONTRACTS.md format requirements:
    {"track_id":"v_0092","bbox":{"x":300,"y":200,"w":180,"h":120},"vehicle_class":"truck",
     "camera_id":"CAM-07","timestamp":"2026-08-30T02:14:40Z","confidence":0.87,
     "model_version":"yolo26-nano-v1"}
    """
    event = {
        "track_id": track_id,
        "bbox": bbox,
        "vehicle_class": vehicle_class,
        "camera_id": camera_id,
        "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        "confidence": round(confidence, 2),
        "model_version": model_version
    }
    return json.dumps(event)
