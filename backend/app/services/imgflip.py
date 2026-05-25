import re
from pathlib import Path
from typing import Any

import httpx

from backend.app.config import Settings


class ImgflipMemeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_dir = settings.uploads_dir / "imgflip-memes"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def enabled(self) -> bool:
        return (
            self.settings.enable_imgflip_memes
            and self.settings.meme_template_provider.lower() == "imgflip"
            and bool(self.settings.imgflip_username)
            and bool(self.settings.imgflip_password)
        )

    def create_meme_image(self, run_id: int, content: dict[str, Any]) -> Path | None:
        if not self.enabled():
            return None

        meme = content.get("meme") or {}
        top_text = self._clean_text(meme.get("top_text") or content["topic"].get("hook") or "")
        bottom_text = self._clean_text(meme.get("bottom_text") or f"{self.settings.product_name}: control ek jagah")
        template_id = self._choose_template_id(meme.get("template_hint", ""))

        response = httpx.post(
            "https://api.imgflip.com/caption_image",
            data={
                "template_id": template_id,
                "username": self.settings.imgflip_username,
                "password": self.settings.imgflip_password,
                "text0": top_text[:120],
                "text1": bottom_text[:120],
                "font": self.settings.imgflip_font,
                "max_font_size": str(self.settings.imgflip_max_font_size),
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(f"Imgflip meme creation failed: {payload.get('error_message')}")

        image_url = payload["data"]["url"]
        image_response = httpx.get(image_url, timeout=60)
        image_response.raise_for_status()
        extension = ".png" if "png" in image_response.headers.get("content-type", "") else ".jpg"
        image_path = self.output_dir / f"servizephyr-meme-{run_id}{extension}"
        image_path.write_bytes(image_response.content)
        return image_path

    def create_meme_story_images(self, run_id: int, content: dict[str, Any]) -> list[Path]:
        if not self.enabled():
            return []

        frames = self._story_frames(content)[: self.settings.meme_story_frames]
        images: list[Path] = []
        for index, frame in enumerate(frames, start=1):
            top_text = self._clean_text(frame["top_text"])
            bottom_text = self._clean_text(frame["bottom_text"])
            template_id = frame["template_id"]
            response = httpx.post(
                "https://api.imgflip.com/caption_image",
                data={
                    "template_id": template_id,
                    "username": self.settings.imgflip_username,
                    "password": self.settings.imgflip_password,
                    "text0": top_text[:85],
                    "text1": bottom_text[:85],
                    "font": self.settings.imgflip_font,
                    "max_font_size": str(min(self.settings.imgflip_max_font_size, 42)),
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success"):
                continue

            image_response = httpx.get(payload["data"]["url"], timeout=60)
            image_response.raise_for_status()
            extension = ".png" if "png" in image_response.headers.get("content-type", "") else ".jpg"
            image_path = self.output_dir / f"servizephyr-meme-{run_id}-{index:02d}{extension}"
            image_path.write_bytes(image_response.content)
            images.append(image_path)
        return images

    def _choose_template_id(self, hint: str) -> str:
        configured = [item.strip() for item in self.settings.imgflip_template_ids.split(",") if item.strip()]
        if not configured:
            configured = ["181913649", "112126428", "87743020", "97984", "102156234", "61579", "101470"]

        hint = hint.lower()
        mapping = {
            "drake": "181913649",
            "two buttons": "87743020",
            "distracted": "112126428",
            "waiting": "4087833",
            "one does not simply": "61579",
            "ancient aliens": "101470",
            "change my mind": "129242436",
            "expanding brain": "93895088",
            "success kid": "61544",
            "disaster girl": "97984",
        }
        for key, template_id in mapping.items():
            if key in hint and template_id in configured:
                return template_id
        return configured[0]

    def _story_frames(self, content: dict[str, Any]) -> list[dict[str, str]]:
        meme = content.get("meme") or {}
        if isinstance(meme.get("frames"), list):
            frames = []
            for frame in meme["frames"]:
                if isinstance(frame, dict) and frame.get("top_text") and frame.get("bottom_text"):
                    frames.append(
                        {
                            "top_text": str(frame["top_text"]),
                            "bottom_text": str(frame["bottom_text"]),
                            "template_id": self._choose_template_id(str(frame.get("template_hint", ""))),
                        }
                    )
            if frames:
                fallback_frames = self._fallback_story_frames(content)
                while len(frames) < self.settings.meme_story_frames and fallback_frames:
                    frames.append(fallback_frames.pop(0))
                return frames

        return self._fallback_story_frames(content)

    def _fallback_story_frames(self, content: dict[str, Any]) -> list[dict[str, str]]:
        topic = content.get("topic", {})
        script = content.get("script", {})
        subtitles = script.get("subtitles") or []
        cta = topic.get("cta") or "DM us the word RESTAURANT"
        hook = topic.get("hook") or "Restaurant rush hour"
        return [
            {
                "top_text": "Rush hour starts",
                "bottom_text": hook,
                "template_id": "181913649",
            },
            {
                "top_text": "Customer: order kahan hai?",
                "bottom_text": subtitles[1] if len(subtitles) > 1 else "Staff: kis screen pe dekhein?",
                "template_id": "87743020",
            },
            {
                "top_text": "Owner after 5 min",
                "bottom_text": "Control chahiye, daily drama nahi",
                "template_id": "93895088",
            },
            {
                "top_text": "ServiZephyr Restaurant",
                "bottom_text": f"Orders, billing, waiting - ek jagah. {cta}",
                "template_id": "129242436",
            },
        ]

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", str(text)).strip()
        blocked = ["zomato", "swiggy", "ubereats", "uber eats", "magicpin", "dotpe", "petpooja", "posist"]
        for name in blocked:
            text = re.sub(name, "restaurant app", text, flags=re.IGNORECASE)
        return text
