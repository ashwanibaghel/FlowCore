import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from backend.app.config import get_settings
from backend.app.services.ai_content import ContentGenerationService
from backend.app.services.carousel_renderer import CarouselRenderer
from backend.app.services.meta import MetaPublisher
from backend.app.services.storage import StorageService


IST = ZoneInfo("Asia/Kolkata")


def main() -> None:
    settings = get_settings()
    now_ist = datetime.now(IST)
    run_id = int(datetime.now(timezone.utc).timestamp())
    content = ContentGenerationService(settings).generate_daily_content(
        business_name=os.getenv("REEL_BUSINESS_NAME", "ServiZephyr"),
        niche=os.getenv(
            "REEL_NICHE",
            "restaurant management software for orders, billing, waiting, staff workflow, khata and analytics",
        ),
        target_audience=os.getenv("REEL_TARGET_AUDIENCE", "restaurant and cafe owners in India"),
        brand_tone=os.getenv("REEL_BRAND_TONE", "deeply relatable Hinglish premium restaurant story"),
        content_mode="carousel",
        cta=os.getenv("REEL_CTA", "DM us the word RESTAURANT"),
        previous_posts=[],
        engagement_history={},
        trend_keywords=_trend_keywords_for_slot(now_ist),
    )

    caption = _build_caption(content)
    video_path = CarouselRenderer(settings).render_video(run_id=run_id, content=content, seconds_per_slide=3)
    public_url = StorageService(settings).upload_video(video_path, public_id=f"servizephyr-daily-carousel-{run_id}")
    media_id = MetaPublisher(settings).publish_instagram_reel(video_url=public_url, caption=caption)
    permalink = _fetch_instagram_permalink(settings, media_id)

    print(
        json.dumps(
            {
                "run_id": run_id,
                "slot_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "title": content.get("carousel", {}).get("title") or content["topic"]["reel_topic"],
                "local_video_path": str(video_path),
                "public_video_url": public_url,
                "instagram_media_id": media_id,
                "instagram_permalink": permalink,
                "dry_run": settings.dry_run_publish,
            },
            indent=2,
        )
    )


def _trend_keywords_for_slot(now_ist: datetime) -> list[str]:
    configured = os.getenv("REEL_TREND_KEYWORDS", "").strip()
    if configured:
        return [keyword.strip() for keyword in configured.split(",") if keyword.strip()]

    hour = now_ist.hour
    if hour < 6:
        return ["closing time billing", "daily cash mismatch", "restaurant night audit", "khata confusion"]
    if hour < 13:
        return ["morning prep", "online orders", "staff coordination", "customer waiting"]
    return ["peak hour chaos", "restaurant billing", "table waiting", "delivery order rush"]


def _build_caption(content: dict) -> str:
    caption = content["caption"]["instagram_caption"].strip()
    hashtags = " ".join(content["caption"]["hashtags"])
    return f"{caption}\n\n{hashtags}".strip()


def _fetch_instagram_permalink(settings, media_id: str) -> str:
    if not media_id or media_id.startswith("dry-run"):
        return ""
    publisher = MetaPublisher(settings)
    response = httpx.get(
        f"{publisher.instagram_base}/{media_id}",
        params={"fields": "permalink", "access_token": settings.meta_access_token},
        timeout=30,
    )
    if response.status_code >= 400:
        return ""
    return str(response.json().get("permalink") or "")


if __name__ == "__main__":
    main()
