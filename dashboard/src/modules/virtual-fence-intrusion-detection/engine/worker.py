import os
import json
import redis
from shapely.geometry import Point, Polygon
import time

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

# Load fences from Redis on startup
def load_fences():
    fences = r.get("ibvap:fences")
    if fences:
        data = json.loads(fences)
        loaded_fences = {}
        for cam_id, config in data.items():
            # config["polygon"] is an array of [x%, y%]
            pts = [(pt[0], pt[1]) for pt in config["polygon"]]
            if len(pts) > 2:
                # We use a 100x100 percentage space for Shapely
                loaded_fences["ZONE_" + cam_id.upper()] = {
                    "camera_id": cam_id,
                    "severity": config.get("severity", "critical"),
                    "polygon": Polygon(pts)
                }
        return loaded_fences
    return {}

active_fences = load_fences()

last_alert_time = 0

def evaluate_intrusion(track_event):
    global last_alert_time
    camera_id = track_event.get("camera_id", "unknown_cam")
    
    # HARD CONSTRAINT: Module 5 ONLY processes cam_05
    if camera_id != "cam_05":
        return
    
    # We mock x, y for the simulator's heartbeat.
    # The point is (50, 50) which is 50% X, 50% Y
    x, y = 50, 50 
    pt = Point(x, y)

    # Throttle alerts to 1 every 15 seconds so the UI isn't spammed
    if time.time() - last_alert_time < 15:
        return

    # Check the fence for cam_05
    zone_key = "ZONE_" + camera_id.upper()
    fence = active_fences.get(zone_key)
    
    if fence and fence["polygon"].contains(pt):
        last_alert_time = time.time()
        # Intrusion detected!
        alert = {
            "module": "module_5",
            "event_type": "Intrusion Detected",
            "zone_id": zone_key,
            "severity": fence["severity"],
            "camera_id": camera_id.upper(),
            "timestamp": time.time(),
            "object_id": f"OBJ-{str(time.time()).replace('.', '')[-6:]}",
            "evidence": "Point inside polygon"
        }
        print(f"INTRUSION DETECTED on {camera_id}! Publishing to ibvap_alerts...")
        r.publish("ibvap_alerts", json.dumps(alert))

def run_worker():
    print("Module 5 Geofence Engine Worker Started")
    pubsub = r.pubsub()
    
    # Subscribe to ingestion (raw tracks) and the hot-reload config channel
    pubsub.subscribe(["ibvap_ingestion", "ibvap_config_hotreload"])
    
    for message in pubsub.listen():
        if message["type"] == "message":
            channel = message["channel"].decode("utf-8")
            data = json.loads(message["data"].decode("utf-8"))
            
            if channel == "ibvap_config_hotreload":
                print("Received hot-reload config! Updating in-memory fences.")
                global active_fences
                active_fences = load_fences()
            
            elif channel == "ibvap_ingestion":
                # Evaluate the track against our fences
                evaluate_intrusion(data)

if __name__ == "__main__":
    run_worker()
