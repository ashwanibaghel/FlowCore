import hashlib
import time
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.config import Settings


class StorageService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def upload_video(self, video_path: Path, public_id: str) -> str:
        if self.settings.storage_provider.lower() == "cloudinary":
            return self._upload_cloudinary(video_path, public_id)
        return self._local_url(video_path)

    def _local_url(self, video_path: Path) -> str:
        if self.settings.public_base_url:
            return f"{self.settings.public_base_url.rstrip('/')}/uploads/{video_path.name}"
        return str(video_path.resolve())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _upload_cloudinary(self, video_path: Path, public_id: str) -> str:
        missing = [
            name
            for name, value in {
                "CLOUDINARY_CLOUD_NAME": self.settings.cloudinary_cloud_name,
                "CLOUDINARY_API_KEY": self.settings.cloudinary_api_key,
                "CLOUDINARY_API_SECRET": self.settings.cloudinary_api_secret,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Cloudinary settings: {', '.join(missing)}")

        timestamp = str(int(time.time()))
        params = {
            "folder": self.settings.cloudinary_folder,
            "public_id": public_id,
            "timestamp": timestamp,
        }
        signature_payload = "&".join(f"{key}={params[key]}" for key in sorted(params))
        signature = hashlib.sha1(f"{signature_payload}{self.settings.cloudinary_api_secret}".encode()).hexdigest()

        upload_url = f"https://api.cloudinary.com/v1_1/{self.settings.cloudinary_cloud_name}/video/upload"
        with video_path.open("rb") as file:
            response = httpx.post(
                upload_url,
                data={
                    "api_key": self.settings.cloudinary_api_key,
                    "timestamp": timestamp,
                    "folder": self.settings.cloudinary_folder,
                    "public_id": public_id,
                    "signature": signature,
                    "resource_type": "video",
                },
                files={"file": (video_path.name, file, "video/mp4")},
                timeout=180,
            )
        response.raise_for_status()
        return response.json()["secure_url"]
