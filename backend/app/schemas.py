from pydantic import BaseModel, Field


class DailyRunRequest(BaseModel):
    business_name: str | None = None
    niche: str | None = None
    target_audience: str | None = None
    brand_tone: str | None = None
    content_mode: str | None = None
    cta: str | None = None
    previous_posts: list[str] = Field(default_factory=list)
    engagement_history: dict[str, float | int | str] = Field(default_factory=dict)
    trend_keywords: list[str] = Field(default_factory=list)
    publish_instagram: bool | None = None
    publish_facebook: bool | None = None


class RunResponse(BaseModel):
    run_id: int
    status: str
    message: str


class CarouselResponse(BaseModel):
    title: str
    caption: str
    hashtags: str
    files: list[str]


class CarouselPublishResponse(BaseModel):
    run_id: int
    status: str
    title: str
    caption: str
    hashtags: str
    local_video_path: str
    public_video_url: str
    instagram_media_id: str = ""
    instagram_permalink: str = ""
    published: bool = False


class RunDetail(BaseModel):
    id: int
    status: str
    business_name: str
    niche: str
    target_audience: str
    topic: str
    hook: str
    caption: str
    hashtags: str
    local_video_path: str
    public_video_url: str
    instagram_media_id: str
    facebook_video_id: str
    error_message: str

    class Config:
        from_attributes = True
