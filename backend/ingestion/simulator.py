import cv2
import time
import json
import redis
import os
import argparse
import random
from pathlib import Path

# Connect to Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

def run_simulation(video_path: str, camera_id: str, fps_limit: int = 15):
    """
    Simulates a live RTSP camera feed by reading an MP4 file
    and publishing events to the event bus.
    """
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return

    print(f"Starting simulation for {camera_id} using {video_path}")
    cap = cv2.VideoCapture(video_path)
    
    frame_delay = 1.0 / fps_limit
    frame_count = 0
    
    # Generate a persistent object ID for this session to trigger behavioral logic
    session_object_id = f"OBJ-{random.randint(100000, 999999)}"

    try:
        while cap.isOpened():
            start_time = time.time()
            ret, frame = cap.read()
            
            if not ret:
                print("End of video stream. Looping...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            # Publish a track event that behavioral_worker.py can use
            track_event = {
                "camera_id": camera_id,
                "object_id": session_object_id,
                "frame_number": frame_count,
                "timestamp": time.time(),
                "status": "ingesting",
                "bbox": [100, 100, 200, 200] # Mock bbox
            }
            
            r.publish("ibvap_ingestion", json.dumps(track_event))
            
            frame_count += 1
            if frame_count % 30 == 0:
                print(f"[{camera_id}] Ingested {frame_count} frames for {session_object_id}...")
            
            # Enforce FPS limit
            elapsed = time.time() - start_time
            if elapsed < frame_delay:
                time.sleep(frame_delay - elapsed)
                
    except KeyboardInterrupt:
        print("Simulation stopped manually.")
    finally:
        cap.release()
        print("Simulation ended.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IBVAP Video Stream Simulator")
    parser.add_argument("--video", type=str, required=True, help="Path to mp4 file")
    parser.add_argument("--camera-id", type=str, default="cam_01", help="Camera ID")
    parser.add_argument("--fps", type=int, default=15, help="Simulation FPS limit")
    
    args = parser.parse_args()
    run_simulation(args.video, args.camera_id, args.fps)
