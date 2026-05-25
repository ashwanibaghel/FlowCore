import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import SessionLocal
from backend.app.models import AutomationRun, RunStatus
from backend.app.services.ai_content import ContentGenerationService
from backend.app.services.meta import MetaPublisher
from backend.app.services.storage import StorageService
from backend.app.services.video_renderer import VideoRenderer


def _update(db: Session, run: AutomationRun, **values: Any) -> None:
    for key, value in values.items():
        setattr(run, key, value)
    db.add(run)
    db.commit()
    db.refresh(run)


def run_daily_reel_pipeline(run_id: int, payload: dict[str, Any]) -> None:
    settings = get_settings()
    db = SessionLocal()
    run = db.get(AutomationRun, run_id)
    if not run:
        db.close()
        return

    try:
        _update(db, run, status=RunStatus.generating.value, attempts=run.attempts + 1)
        ai = ContentGenerationService(settings)
        content = ai.generate_daily_content(
            business_name=run.business_name,
            niche=run.niche,
            target_audience=run.target_audience,
            brand_tone=payload.get("brand_tone") or settings.default_brand_tone,
            content_mode=payload.get("content_mode") or settings.default_content_mode,
            cta=payload.get("cta") or settings.default_cta,
            previous_posts=payload.get("previous_posts") or [],
            engagement_history=payload.get("engagement_history") or {},
            trend_keywords=payload.get("trend_keywords") or [],
        )

        _update(
            db,
            run,
            topic=content["topic"]["reel_topic"],
            hook=content["topic"]["hook"],
            pain_point=content["topic"]["audience_pain_point"],
            cta=content["topic"]["cta"],
            idea_summary=content["topic"]["idea_summary"],
            script_json=json.dumps(content["script"], ensure_ascii=True),
            caption=content["caption"]["instagram_caption"],
            hashtags=" ".join(content["caption"]["hashtags"]),
            video_prompt_json=json.dumps(content["video_prompts"], ensure_ascii=True),
        )

        _update(db, run, status=RunStatus.rendering.value)
        renderer = VideoRenderer(settings)
        video_path = renderer.render_reel(run_id=run.id, content=content)
        _update(db, run, local_video_path=str(video_path))

        _update(db, run, status=RunStatus.uploading.value)
        storage = StorageService(settings)
        public_url = storage.upload_video(video_path, public_id=f"daily-reel-{run.id}")
        _update(db, run, public_video_url=public_url)

        _update(db, run, status=RunStatus.publishing.value)
        publisher = MetaPublisher(settings)

        publish_ig = payload.get("publish_instagram")
        if publish_ig is None:
            publish_ig = settings.auto_publish_instagram
        publish_fb = payload.get("publish_facebook")
        if publish_fb is None:
            publish_fb = settings.auto_publish_facebook

        instagram_media_id = ""
        facebook_video_id = ""
        if publish_ig:
            instagram_media_id = publisher.publish_instagram_reel(
                video_url=public_url,
                caption=f"{run.caption}\n\n{run.hashtags}".strip(),
            )
        if publish_fb:
            facebook_video_id = publisher.publish_facebook_video(
                video_url=public_url,
                description=f"{run.caption}\n\n{run.hashtags}".strip(),
            )

        _update(
            db,
            run,
            status=RunStatus.completed.value,
            instagram_media_id=instagram_media_id,
            facebook_video_id=facebook_video_id,
            completed_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        _update(db, run, status=RunStatus.failed.value, error_message=str(exc))
    finally:
        db.close()
