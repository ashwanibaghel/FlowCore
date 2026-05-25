from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class RunStatus(str, Enum):
    queued = "queued"
    generating = "generating"
    rendering = "rendering"
    uploading = "uploading"
    publishing = "publishing"
    completed = "completed"
    failed = "failed"


class AutomationRun(Base):
    __tablename__ = "automation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.queued.value, index=True)
    business_name: Mapped[str] = mapped_column(String(255))
    niche: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    trend_keywords: Mapped[str] = mapped_column(Text, default="")

    topic: Mapped[str] = mapped_column(Text, default="")
    hook: Mapped[str] = mapped_column(Text, default="")
    pain_point: Mapped[str] = mapped_column(Text, default="")
    cta: Mapped[str] = mapped_column(Text, default="")
    idea_summary: Mapped[str] = mapped_column(Text, default="")
    script_json: Mapped[str] = mapped_column(Text, default="{}")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(Text, default="")
    video_prompt_json: Mapped[str] = mapped_column(Text, default="{}")

    local_video_path: Mapped[str] = mapped_column(Text, default="")
    public_video_url: Mapped[str] = mapped_column(Text, default="")
    instagram_media_id: Mapped[str] = mapped_column(String(255), default="")
    facebook_video_id: Mapped[str] = mapped_column(String(255), default="")

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

