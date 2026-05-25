import json
from datetime import datetime, timezone

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db, init_db
from backend.app.models import AutomationRun, RunStatus
from backend.app.pipeline import run_daily_reel_pipeline
from backend.app.schemas import CarouselPublishResponse, CarouselResponse, DailyRunRequest, RunDetail, RunResponse
from backend.app.services.ai_content import ContentGenerationService
from backend.app.services.carousel_renderer import CarouselRenderer
from backend.app.services.meta import MetaPublisher
from backend.app.services.storage import StorageService

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.post("/api/v1/runs/daily", response_model=RunResponse)
def create_daily_run(
    payload: DailyRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RunResponse:
    run = AutomationRun(
        status=RunStatus.queued.value,
        business_name=payload.business_name or settings.default_business_name,
        niche=payload.niche or settings.default_niche,
        target_audience=payload.target_audience or settings.default_target_audience,
        trend_keywords=", ".join(payload.trend_keywords),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_daily_reel_pipeline, run.id, payload.model_dump())
    return RunResponse(run_id=run.id, status=run.status, message="Daily reel automation queued.")


@app.get("/api/v1/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)) -> AutomationRun:
    run = db.get(AutomationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/v1/runs", response_model=list[RunDetail])
def list_runs(db: Session = Depends(get_db)) -> list[AutomationRun]:
    return db.query(AutomationRun).order_by(AutomationRun.id.desc()).limit(50).all()


@app.post("/api/v1/carousels/sample", response_model=CarouselResponse)
def create_sample_carousel(payload: DailyRunRequest) -> CarouselResponse:
    content = ContentGenerationService(settings).generate_daily_content(
        business_name=payload.business_name or "ServiZephyr Restaurant",
        niche=payload.niche or settings.default_niche,
        target_audience=payload.target_audience or settings.default_target_audience,
        brand_tone=payload.brand_tone or "funny relatable Hinglish premium restaurant story",
        content_mode=payload.content_mode or "carousel",
        cta=payload.cta or "DM us the word RESTAURANT",
        previous_posts=payload.previous_posts,
        engagement_history=payload.engagement_history,
        trend_keywords=payload.trend_keywords,
    )
    paths = CarouselRenderer(settings).render(run_id=0, content=content)
    return CarouselResponse(
        title=content.get("carousel", {}).get("title") or content["topic"]["reel_topic"],
        caption=content["caption"]["instagram_caption"],
        hashtags=" ".join(content["caption"]["hashtags"]),
        files=[str(path) for path in paths],
    )


def _verify_automation_secret(x_automation_secret: str | None = Header(default=None)) -> None:
    if settings.automation_secret and x_automation_secret != settings.automation_secret:
        raise HTTPException(status_code=401, detail="Invalid automation secret")


@app.post("/api/v1/carousels/daily-publish", response_model=CarouselPublishResponse)
def create_and_publish_carousel(
    payload: DailyRunRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_automation_secret),
) -> CarouselPublishResponse:
    business_name = payload.business_name or "ServiZephyr"
    niche = (
        payload.niche
        or "restaurant management software for orders, billing, waiting, staff workflow, khata and analytics"
    )
    target_audience = payload.target_audience or "restaurant and cafe owners in India"
    trend_keywords = payload.trend_keywords or [
        "peak hour chaos",
        "restaurant billing",
        "customer waiting",
        "online orders",
    ]
    publish_instagram = payload.publish_instagram if payload.publish_instagram is not None else settings.auto_publish_instagram

    run = AutomationRun(
        status=RunStatus.generating.value,
        business_name=business_name,
        niche=niche,
        target_audience=target_audience,
        trend_keywords=", ".join(trend_keywords),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        content = ContentGenerationService(settings).generate_daily_content(
            business_name=business_name,
            niche=niche,
            target_audience=target_audience,
            brand_tone=payload.brand_tone or "deeply relatable Hinglish premium restaurant story",
            content_mode=payload.content_mode or "carousel",
            cta=payload.cta or "DM us the word RESTAURANT",
            previous_posts=payload.previous_posts,
            engagement_history=payload.engagement_history,
            trend_keywords=trend_keywords,
        )

        caption = _build_caption(content)
        hashtags = " ".join(content["caption"]["hashtags"])
        run.topic = content["topic"]["reel_topic"]
        run.hook = content["topic"]["hook"]
        run.pain_point = content["topic"]["audience_pain_point"]
        run.cta = content["topic"]["cta"]
        run.idea_summary = content["topic"]["idea_summary"]
        run.script_json = json.dumps(content.get("carousel") or content.get("script") or {}, ensure_ascii=True)
        run.caption = caption
        run.hashtags = hashtags
        run.video_prompt_json = json.dumps(content.get("video_prompts") or {}, ensure_ascii=True)

        run.status = RunStatus.rendering.value
        db.commit()
        video_path = CarouselRenderer(settings).render_video(run_id=run.id, content=content, seconds_per_slide=3)
        run.local_video_path = str(video_path)

        run.status = RunStatus.uploading.value
        db.commit()
        public_url = StorageService(settings).upload_video(video_path, public_id=f"servizephyr-daily-carousel-{run.id}")
        run.public_video_url = public_url

        instagram_media_id = ""
        instagram_permalink = ""
        if publish_instagram:
            run.status = RunStatus.publishing.value
            db.commit()
            instagram_media_id = MetaPublisher(settings).publish_instagram_reel(video_url=public_url, caption=caption)
            instagram_permalink = _fetch_instagram_permalink(instagram_media_id)
            run.instagram_media_id = instagram_media_id

        run.status = RunStatus.completed.value
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        return CarouselPublishResponse(
            run_id=run.id,
            status=run.status,
            title=content.get("carousel", {}).get("title") or content["topic"]["reel_topic"],
            caption=caption,
            hashtags=hashtags,
            local_video_path=str(video_path),
            public_video_url=public_url,
            instagram_media_id=instagram_media_id,
            instagram_permalink=instagram_permalink,
            published=bool(instagram_media_id),
        )
    except Exception as exc:
        run.status = RunStatus.failed.value
        run.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _build_caption(content: dict) -> str:
    caption = content["caption"]["instagram_caption"].strip()
    hashtags = " ".join(content["caption"]["hashtags"])
    return f"{caption}\n\n{hashtags}".strip()


def _fetch_instagram_permalink(media_id: str) -> str:
    if not media_id or media_id.startswith("dry-run"):
        return ""
    instagram_base = MetaPublisher(settings).instagram_base
    response = httpx.get(
        f"{instagram_base}/{media_id}",
        params={"fields": "permalink", "access_token": settings.meta_access_token},
        timeout=30,
    )
    if response.status_code >= 400:
        return ""
    return str(response.json().get("permalink") or "")
