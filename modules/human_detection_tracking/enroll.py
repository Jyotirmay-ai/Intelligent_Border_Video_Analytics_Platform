import os
import sys
import argparse
import logging
import cv2
import numpy as np
from tqdm import tqdm

# Add project root to path to allow imports from human_detection_tracking
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from human_detection_tracking.config import (
    DATASET_PATH, EMBEDDINGS_PATH, WEBcam_SAMPLES_COUNT,
    FACE_YUNET_MODEL_PATH, FACE_YUNET_SCORE_THRESHOLD, FACE_YUNET_NMS_THRESHOLD,
    FACE_INSIGHTFACE_MODEL_PACK
)
from human_detection_tracking.utils import (
    load_embeddings_db, save_embeddings_db, validate_dataset_dir
)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s")

def process_image(img_bgr, detector, embedder):
    """Extract the largest face embedding directly from the full image."""
    if embedder is None:
        return None
    detected_faces = embedder.get(img_bgr)
    if not detected_faces:
        return None
    best_face = max(detected_faces, key=lambda face: float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])))
    return best_face.embedding

def enroll_from_directory(config, detector, embedder):
    """Enroll identities from dataset/<person_name>/ folders."""
    dataset_dir = config["dataset_path"]
    db_path = config["embeddings_path"]
    person_images = validate_dataset_dir(dataset_dir)
    if not person_images:
        logging.warning(f"No valid identities found in '{dataset_dir}'.")
        return
    
    identities = load_embeddings_db(db_path)
    db = {"version": 1, "identities": identities}
    
    total_enrolled = 0
    for person_name, img_paths in person_images.items():
        logging.info(f"Processing '{person_name}'...")
        embeddings_list = []
        for img_path in tqdm(img_paths, desc=f"Enrolling {person_name}"):
            img = cv2.imread(img_path)
            if img is None: continue
            emb = process_image(img, detector, embedder)
            if emb is not None: embeddings_list.append(emb)
        
        if embeddings_list:
            embeddings_arr = np.array(embeddings_list)
            mean_emb = np.mean(embeddings_arr, axis=0)
            norm = np.linalg.norm(mean_emb)
            if norm > 0: mean_emb = mean_emb / norm
            db["identities"][person_name] = {"mean_embedding": mean_emb, "embeddings": embeddings_list}
            total_enrolled += 1
            
    if total_enrolled > 0:
        save_embeddings_db(db_path, db)
        logging.info(f"Enrollment complete. Total identities: {len(db['identities'])}.")

def enroll_from_webcam(config, detector, embedder, name=None):
    """Enroll identity from live webcam."""
    if not name:
        name = input("Enter person name for enrollment: ").strip()
    if not name: return
    
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()
    target_dir = os.path.join(config["dataset_path"], safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(config["camera_source"])
    samples_required = config.get("webcam_samples_count", 8)
    captured_embeddings = []
    sample_counter = 0

    logging.info(f"LIVE ENROLLMENT FOR: {safe_name}")
    while True:
        ret, frame = cap.read()
        if not ret: break
        display_frame = frame.copy()
        faces = detector.detect(frame, det_scale=config.get("det_scale", 0.5))
        
        face_detected = len(faces) > 0
        for f in faces:
            x, y, w, h = f["box"]
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0) if face_detected else (0, 0, 255), 2)
        
        cv2.putText(display_frame, f"Enrolling: {safe_name} ({sample_counter}/{samples_required})", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow("Live Enrollment", display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27): break
        elif key in (ord('c'), 32) and face_detected:
            emb = process_image(frame, detector, embedder)
            if emb is not None:
                captured_embeddings.append(emb)
                sample_counter += 1
                cv2.imwrite(os.path.join(target_dir, f"sample_{sample_counter:02d}.jpg"), frame)
                if sample_counter >= samples_required: break

    cap.release()
    cv2.destroyAllWindows()

    if captured_embeddings:
        db_path = config["embeddings_path"]
        db = load_embeddings_db(db_path)
        if "identities" not in db: db = {"version": 1, "identities": {}}
        embeddings_arr = np.array(captured_embeddings)
        mean_emb = np.mean(embeddings_arr, axis=0)
        norm = np.linalg.norm(mean_emb)
        if norm > 0: mean_emb = mean_emb / norm
        db["identities"][safe_name] = {"mean_embedding": mean_emb, "embeddings": captured_embeddings}
        save_embeddings_db(db_path, db)
        logging.info(f"Enrolled '{safe_name}' successfully.")

def main():
    parser = argparse.ArgumentParser(description="Real-Time Face Recognition - Enrollment")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--webcam", action="store_true")
    parser.add_argument("--name", type=str, default=None, help="Name used with --webcam enrollment")
    args = parser.parse_args()
    
    from human_detection_tracking.config import (
        DATASET_PATH, EMBEDDINGS_PATH, FACE_YUNET_MODEL_PATH, 
        FACE_YUNET_SCORE_THRESHOLD, FACE_YUNET_NMS_THRESHOLD, 
        FACE_INSIGHTFACE_MODEL_PACK, WEBcam_SAMPLES_COUNT
    )
    
    config = {
        "dataset_path": DATASET_PATH,
        "embeddings_path": EMBEDDINGS_PATH,
        "yunet_model_path": FACE_YUNET_MODEL_PATH,
        "yunet_score_threshold": FACE_YUNET_SCORE_THRESHOLD,
        "yunet_nms_threshold": FACE_YUNET_NMS_THRESHOLD,
        "insightface_model_pack": FACE_INSIGHTFACE_MODEL_PACK,
        "webcam_samples_count": WEBcam_SAMPLES_COUNT,
        "camera_source": 0,
        "det_scale": 0.5
    }

    from human_detection_tracking.main import init_human_detector, init_face_detector, init_insightface_embedder
    # In the merged module, we use the same init functions
    detector = init_face_detector()
    embedder = init_insightface_embedder()

    if args.webcam:
        enroll_from_webcam(config, detector, embedder, name=args.name)
    else:
        enroll_from_directory(config, detector, embedder)

if __name__ == "__main__":
    main()
