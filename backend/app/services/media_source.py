import re
from pathlib import Path
from random import choice
from typing import Any

import httpx

from backend.app.config import Settings


class PexelsMediaSource:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache_dir = settings.uploads_dir / "pexels-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_scene_clips(self, scenes: list[dict[str, Any]], run_id: int) -> list[Path]:
        clips: list[Path] = []
        if not self.settings.pexels_api_key:
            return clips

        for index, scene in enumerate(scenes, start=1):
            query = self._query_for_scene(scene)
            try:
                clip = self._download_clip(query=query, run_id=run_id, scene_index=index)
            except Exception:
                clip = None
            if clip:
                clips.append(clip)
        return clips

    def get_carousel_backgrounds(self, slides: list[dict[str, Any]], run_id: int) -> list[Path | None]:
        backgrounds: list[Path | None] = []
        if not self.settings.pexels_api_key:
            return [None for _ in slides]

        for index, slide in enumerate(slides, start=1):
            if self._should_skip_background(slide):
                backgrounds.append(None)
                continue
            query = self._query_for_slide(slide)
            try:
                backgrounds.append(self._download_photo(query=query, run_id=run_id, slide_index=index))
            except Exception:
                backgrounds.append(None)
        return backgrounds

    def _should_skip_background(self, slide: dict[str, Any]) -> bool:
        tag = str(slide.get("tag") or slide.get("role") or "").upper()
        role = str(slide.get("role") or "").lower()
        slide_number = int(slide.get("slide_number") or slide.get("slide") or 0)
        visual = str(slide.get("visual_direction") or "").lower()
        return tag == "CTA" or role == "cta" or slide_number == 7 or "no photo" in visual or "brand end card" in visual

    def _query_for_scene(self, scene: dict[str, Any]) -> str:
        text = " ".join(
            [
                str(scene.get("visual", "")),
                str(scene.get("on_screen_text", "")),
                str(scene.get("voiceover", "")),
            ]
        ).lower()
        if any(word in text for word in ["salon", "beauty", "hair"]):
            return "salon owner phone vertical"
        if any(word in text for word in ["clinic", "doctor", "patient"]):
            return "clinic reception phone vertical"
        if any(word in text for word in ["message", "reply", "follow"]):
            return "business owner texting phone vertical"
        if any(word in text for word in ["dashboard", "automation", "workflow"]):
            return "business dashboard laptop vertical"
        if any(word in text for word in ["customer", "client", "sales"]):
            return "small business customer service vertical"
        return "small business owner working phone vertical"

    def _download_clip(self, query: str, run_id: int, scene_index: int) -> Path | None:
        response = httpx.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": self.settings.pexels_api_key},
            params={"query": query, "orientation": "portrait", "per_page": 8},
            timeout=30,
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])
        if not videos:
            return None

        video = videos[(scene_index - 1) % len(videos)]
        files = video.get("video_files", [])
        mp4_files = [item for item in files if item.get("file_type") == "video/mp4" and item.get("link")]
        if not mp4_files:
            return None

        mp4_files.sort(key=lambda item: abs((item.get("width") or 540) - 540) + abs((item.get("height") or 960) - 960))
        selected = mp4_files[0]
        safe_query = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:42]
        path = self.cache_dir / f"run-{run_id}-scene-{scene_index}-{safe_query}-{video.get('id')}.mp4"
        if path.exists() and path.stat().st_size > 0:
            return path

        with httpx.stream("GET", selected["link"], timeout=120) as stream:
            stream.raise_for_status()
            with path.open("wb") as file:
                for chunk in stream.iter_bytes():
                    file.write(chunk)
        return path

    def _query_for_slide(self, slide: dict[str, Any]) -> str:
        return self._restaurant_safe_slide_query(slide)

    def _restaurant_safe_slide_query(self, slide: dict[str, Any]) -> str:
        tag = str(slide.get("tag") or slide.get("role") or "").upper()
        role = str(slide.get("role") or "").lower()
        slide_number = int(slide.get("slide_number") or slide.get("slide") or 0)
        raw_query = str(slide.get("pexels_query") or slide.get("visual_direction") or "").lower()

        mapping = {
            1: ["busy restaurant counter staff", "crowded cafe counter", "restaurant rush hour counter"],
            2: ["restaurant cashier counter", "takeaway restaurant counter", "restaurant payment counter"],
            3: ["busy restaurant kitchen chefs cooking", "restaurant kitchen staff cooking", "chef preparing food restaurant"],
            4: ["stressed restaurant manager holding head", "tired cafe owner paperwork", "restaurant owner working late"],
            5: ["restaurant manager tablet", "restaurant staff tablet order", "restaurant kitchen chefs"],
            6: ["digital pos terminal restaurant billing", "restaurant manager tablet", "restaurant cashier pos terminal"],
            7: ["restaurant owner smiling cafe", "happy cafe owner restaurant", "restaurant owner standing cafe"],
        }
        tag_mapping = {
            "HOOK": mapping[1],
            "STORY": mapping[2],
            "PAIN_POINT": mapping[2],
            "CONFLICT": mapping[3],
            "EMOTION": mapping[4],
            "SOLUTION": mapping[5],
            "BENEFIT": mapping[6],
            "CTA": mapping[7],
        }
        role_mapping = {
            "hook": mapping[1],
            "story": mapping[2],
            "conflict": mapping[3],
            "emotion": mapping[4],
            "solution": mapping[5],
            "benefit": mapping[6],
            "cta": mapping[7],
        }

        restaurant_words = ["restaurant", "cafe", "kitchen", "waiter", "chef", "food", "billing", "pos"]
        bad_words = ["traffic", "road", "street", "office", "corporate", "businessman", "laptop office", "city"]
        if any(word in raw_query for word in bad_words):
            raw_query = ""
        if tag in tag_mapping:
            return choice(tag_mapping[tag])
        if role in role_mapping:
            return choice(role_mapping[role])
        if slide_number in mapping:
            return choice(mapping[slide_number])
        is_restaurant_specific = raw_query and any(word in raw_query for word in restaurant_words)
        if is_restaurant_specific:
            return raw_query
        return "busy restaurant counter staff"

    def _legacy_query_for_slide(self, slide: dict[str, Any]) -> str:
        text = " ".join(
            [
                str(slide.get("headline", "")),
                str(slide.get("body", "")),
                str(slide.get("visual_direction", "")),
                str(slide.get("role", "")),
                str(slide.get("emotion", "")),
            ]
        ).lower()
        if any(word in text for word in ["kitchen", "chef", "order"]):
            return "restaurant kitchen busy"
        if any(word in text for word in ["billing", "cashier", "counter"]):
            return "restaurant cashier counter"
        if any(word in text for word in ["customer", "waiting", "table"]):
            return "restaurant customer waiting table"
        if any(word in text for word in ["dashboard", "system", "control", "solution"]):
            return "restaurant manager tablet"
        if any(word in text for word in ["crowded", "rush", "peak"]):
            return "busy restaurant evening"
        return "restaurant owner working"

    def _download_photo(self, query: str, run_id: int, slide_index: int) -> Path | None:
        response = httpx.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": self.settings.pexels_api_key},
            params={"query": query, "orientation": "portrait", "per_page": 8},
            timeout=30,
        )
        response.raise_for_status()
        photos = response.json().get("photos", [])
        if not photos:
            return None
        photo = choice(photos)
        src = photo.get("src", {})
        image_url = src.get("large2x") or src.get("large") or src.get("portrait") or src.get("original")
        if not image_url:
            return None
        safe_query = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:42]
        path = self.cache_dir / f"run-{run_id}-slide-{slide_index}-{safe_query}-{photo.get('id')}.jpg"
        if path.exists() and path.stat().st_size > 0:
            return path
        image_response = httpx.get(image_url, timeout=60)
        image_response.raise_for_status()
        path.write_bytes(image_response.content)
        return path
