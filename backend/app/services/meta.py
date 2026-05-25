import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.config import Settings


class MetaPublisher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.instagram_base = self._instagram_graph_base()
        self.graph_base = f"https://graph.facebook.com/{settings.meta_graph_version}"
        self.video_base = f"https://graph-video.facebook.com/{settings.meta_graph_version}"

    def _instagram_graph_base(self) -> str:
        if self.settings.meta_access_token.startswith("IG"):
            return f"https://graph.instagram.com/{self.settings.meta_graph_version}"
        return f"https://graph.facebook.com/{self.settings.meta_graph_version}"

    def publish_instagram_reel(self, video_url: str, caption: str) -> str:
        if self.settings.dry_run_publish:
            return "dry-run-instagram-media-id"
        if not self.settings.meta_access_token or not self.settings.instagram_account_id:
            raise RuntimeError("Missing META_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID")
        if not video_url.startswith("http"):
            raise RuntimeError("Instagram publishing needs a public HTTPS video URL. Use Cloudinary or S3.")

        container_id = self._create_instagram_container(video_url=video_url, caption=caption)
        self._wait_for_instagram_container(container_id)
        return self._publish_instagram_container(container_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _create_instagram_container(self, video_url: str, caption: str) -> str:
        response = httpx.post(
            f"{self.instagram_base}/{self.settings.instagram_account_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
                "access_token": self.settings.meta_access_token,
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["id"]

    def _wait_for_instagram_container(self, container_id: str) -> None:
        for _ in range(24):
            response = httpx.get(
                f"{self.instagram_base}/{container_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.settings.meta_access_token,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            status_code = payload.get("status_code")
            if status_code == "FINISHED":
                return
            if status_code == "ERROR":
                raise RuntimeError(f"Instagram container processing failed: {payload}")
            time.sleep(5)
        raise TimeoutError("Instagram container did not finish processing in time.")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _publish_instagram_container(self, container_id: str) -> str:
        response = httpx.post(
            f"{self.instagram_base}/{self.settings.instagram_account_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": self.settings.meta_access_token,
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["id"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def publish_facebook_video(self, video_url: str, description: str) -> str:
        if self.settings.dry_run_publish:
            return "dry-run-facebook-video-id"
        if not self.settings.facebook_page_id:
            raise RuntimeError("Missing FACEBOOK_PAGE_ID")
        access_token = self.settings.facebook_page_access_token or self.settings.meta_access_token
        if not access_token:
            raise RuntimeError("Missing FACEBOOK_PAGE_ACCESS_TOKEN or META_ACCESS_TOKEN")
        if not video_url.startswith("http"):
            raise RuntimeError("Facebook publishing needs a public video URL. Use Cloudinary or S3.")

        response = httpx.post(
            f"{self.video_base}/{self.settings.facebook_page_id}/videos",
            data={
                "file_url": video_url,
                "description": description,
                "access_token": access_token,
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["id"]
