from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FlowCore AI Automation MVP"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    public_base_url: str = ""
    log_level: str = "INFO"
    automation_secret: str = ""

    database_url: str = "sqlite:///./flowcore.sqlite3"

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_site_url: str = "https://flowcore.ai"
    openrouter_app_name: str = "FlowCore"

    storage_provider: str = "local"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "flowcore/reels"

    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    meme_template_provider: str = "imgflip"
    enable_imgflip_memes: bool = True
    imgflip_username: str = ""
    imgflip_password: str = ""
    imgflip_template_ids: str = "181913649,112126428,87743020,97984,102156234,61579,101470,27813981"
    imgflip_font: str = "impact"
    imgflip_max_font_size: int = 50
    meme_story_frames: int = 4
    meme_frame_seconds: int = 3
    enable_meme_voiceover: bool = False
    enable_generated_music: bool = True

    tts_provider: str = "edge"
    edge_tts_voice: str = "en-IN-PrabhatNeural"
    edge_tts_rate: str = "+0%"
    edge_tts_volume: str = "+0%"
    sapi_tts_voice: str = "Microsoft Zira Desktop"
    sapi_tts_rate: int = 1

    music_dir: Path = Field(default=Path("assets/music"))
    sfx_dir: Path = Field(default=Path("assets/sfx"))
    brand_logo_path: Path = Field(default=Path("assets/brand/logo.png"))
    enable_background_music: bool = True
    background_music_volume: float = 0.18
    voiceover_volume: float = 1.0

    meta_graph_version: str = "v25.0"
    meta_access_token: str = ""
    instagram_account_id: str = ""
    auto_publish_instagram: bool = False

    facebook_page_id: str = ""
    facebook_page_access_token: str = ""
    auto_publish_facebook: bool = False

    default_business_name: str = "FlowCore"
    default_niche: str = "AI automation services for small businesses"
    default_target_audience: str = "small business owners"
    default_brand_tone: str = "clear, practical, friendly, confident"
    default_cta: str = "DM us the word AUTOMATE"
    default_content_mode: str = "meme"
    product_name: str = "ServiZephyr Restaurant"

    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    video_scene_seconds: int = 4
    video_background_color: str = "#111827"
    video_accent_color: str = "#22c55e"
    ffmpeg_binary: str = "ffmpeg"

    dry_run_publish: bool = True

    uploads_dir: Path = Field(default=Path("uploads"))
    logs_dir: Path = Field(default=Path("logs"))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.music_dir.mkdir(parents=True, exist_ok=True)
    settings.sfx_dir.mkdir(parents=True, exist_ok=True)
    return settings
