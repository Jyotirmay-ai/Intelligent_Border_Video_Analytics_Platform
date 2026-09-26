import os
import sys
import pickle
import numpy as np
import cv2
import logging
from pathlib import Path
from .config import (
    DATASET_PATH,
    EMBEDDINGS_PATH,
    WEBcam_SAMPLES_COUNT,
    FACE_YUNET_MODEL_PATH,
    FACE_YUNET_SCORE_THRESHOLD,
    FACE_YUNET_NMS_THRESHOLD,
    FACE_INSIGHTFACE_MODEL_PACK
)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message) 함께-message")

# Reference facial landmarks for 112x112 ArcFace alignment
ARCFACE_REF_PTS_YUNET = np.array([
    [73.5318, 51.5014],  # right eye
    [38.2946, 51.6963],  # left eye
    [56.0252, 71.7366],  # nose tip
    [70.7299, 92.2041],  # right mouth corner
    [41.5493, 92.3655]   # left mouth corner
], dtype=np.float32)

def align_face(image, landmarks, output_size=(112, 112)):
    """Perform similarity transformation to align face landmarks to ArcFace reference points."""
    src_pts = landmarks.astype(np.float32)
    dst_pts = ARCFACE_REF_PTS_YUNET.copy()
    tfm, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
    if tfm is None:
        return cv2.resize(image, output_size)
    return cv2.warpAffine(image, tfm, output_size, flags=cv2.INTER_LINEAR)

def compute_cosine_similarity(emb1, emb2):
    """Compute cosine similarity score between two L2-normalized 1D embeddings."""
    return float(np.dot(emb1, emb2))

def load_embeddings_db(path=EMBEDDINGS_PATH):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
            return data.get("identities", {}) if isinstance(data, dict) else {}
    except Exception as e:
        logging.error(f"Error reading embeddings file {path}: {e}")
        return {}

def save_embeddings_db(db_path, db_data):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with open(db_path, "wb") as f:
        pickle.dump(db_data, f)

def validate_dataset_dir(dataset_dir):
    path = Path(dataset_dir)
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    person_images = {}
    if not path.exists() or not path.is_dir():
        return person_images
    for subfolder in path.iterdir():
        if subfolder.is_dir():
            images = [str(img_file) for img_file in subfolder.iterdir() if img_file.is_file() and img_file.suffix.lower() in valid_extensions]
            if images: person_images[subfolder.name] = images
    return person_images

class CentroidTracker:
    def __init__(self, max_disappeared=5):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.metadata = {}
        self.max_disappeared = max_disappeared

    def register(self, centroid, box, name, score):
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.metadata[self.next_object_id] = {"box": box, "name": name, "score": score}
        self.next_object_id += 1

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]
        del self.metadata[object_id]

    def update(self, detections=None):
        if detections is None:
            to_deregister = []
            for obj_id in self.disappeared:
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared: to_deregister.append(obj_id)
            for obj_id in to_deregister: self.deregister(obj_id)
            return self.get_tracked_results()

        if len(detections) == 0:
            for obj_id in list(self.disappeared.keys()):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared: self.deregister(obj_id)
            return self.get_tracked_results()

        input_centroids = np.zeros((len(detections), 2), dtype="int")
        for i, det in enumerate(detections):
            x, y, w, h = det["box"]
            input_centroids[i] = (int(x + w / 2.0), int(y + h / 2.0))

        if len(self.objects) == 0:
            for i, det in enumerate(detections):
                self.register(input_centroids[i], det["box"], det["name"], det["score"])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())
            D = np.linalg.norm(np.array(object_centroids)[:, np.newaxis] - input_centroids, axis=2)
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]
            used_rows, used_cols = set(), set()
            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols or D[row, col] > 100: continue
                obj_id = object_ids[row]
                self.objects[obj_id] = input_centroids[col]
                self.disappeared[obj_id] = 0
                self.metadata[obj_id] = {"box": detections[col]["box"], "name": detections[col]["name"], "score": detections[col]["score"]}
                used_rows.add(row); used_cols.add(col)
            for row in set(range(0, D.shape[0])).difference(used_rows):
                obj_id = object_ids[row]
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared: self.deregister(obj_id)
            for col in set(range(0, D.shape[1])).difference(used_cols):
                self.register(input_centroids[col], detections[col]["box"], detections[col]["name"], detections[col]["score"])
        return self.get_tracked_results()

    def get_tracked_results(self):
        return [meta for meta in self.metadata.values()]
