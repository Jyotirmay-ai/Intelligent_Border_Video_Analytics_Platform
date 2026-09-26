"""
Snapshot storage — captures JPEG frame and writes it to MinIO/S3 or local disk.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class SnapshotStorage:
    def __init__(
        self,
        mock_enabled: bool,
        local_path: str,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        self._mock_enabled = mock_enabled
        self._local_path = Path(local_path)
        self._endpoint = endpoint
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._s3 = None

        if mock_enabled:
            self._local_path.mkdir(parents=True, exist_ok=True)
        else:
            import boto3
            self._s3 = boto3.client(
                "s3",
                endpoint_url=f"http://{self._endpoint}",
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
            )

    def upload(self, track_id: str, frame: np.ndarray) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{track_id}_{timestamp}.jpg"

        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise RuntimeError("cv2.imencode failed")

        data = buffer.tobytes()

        if self._mock_enabled:
            path = self._local_path / filename
            path.write_bytes(data)
            return str(path.resolve())
        else:
            self._s3.upload_fileobj(
                io.BytesIO(data),
                self._bucket,
                filename,
                ExtraArgs={"ContentType": "image/jpeg"},
            )
            return f"http://{self._endpoint}/{self._bucket}/{filename}"
