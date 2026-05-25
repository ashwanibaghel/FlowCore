import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from random import choice, randint
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from backend.app.config import Settings
from backend.app.services.media_source import PexelsMediaSource


class CarouselRenderer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.width = 1080
        self.height = 1920
        self.output_root = settings.uploads_dir / "carousels"
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.logo = self._load_logo()

    def render(self, run_id: int, content: dict[str, Any]) -> list[Path]:
        carousel = content.get("carousel") or {}
        slides = carousel.get("slides") or []
        if not slides:
            slides = self._fallback_slides(content)
        slides = slides[:7]
        backgrounds = PexelsMediaSource(self.settings).get_carousel_backgrounds(slides=slides, run_id=run_id)

        output_dir = self.output_root / f"servizephyr-carousel-{run_id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "content.json").write_text(json.dumps(content, ensure_ascii=True, indent=2), encoding="utf-8")

        paths: list[Path] = []
        for index, slide in enumerate(slides, start=1):
            path = output_dir / f"slide-{index:02d}.png"
            self._render_slide(
                path=path,
                slide=slide,
                index=index,
                total=len(slides),
                background_path=backgrounds[index - 1] if index - 1 < len(backgrounds) else None,
            )
            paths.append(path)
        return paths

    def render_video(self, run_id: int, content: dict[str, Any], seconds_per_slide: int = 3) -> Path:
        paths = self.render(run_id=run_id, content=content)
        output_dir = paths[0].parent
        scene_paths: list[Path] = []
        for index, slide_path in enumerate(paths, start=1):
            scene_path = output_dir / f"video-scene-{index:02d}.mp4"
            self._render_video_scene(slide_path=slide_path, output_path=scene_path, duration=seconds_per_slide)
            scene_paths.append(scene_path)

        silent_output = output_dir / "servizephyr-carousel-story-silent.mp4"
        final_output = output_dir / "servizephyr-carousel-story.mp4"
        self._crossfade_scenes(scene_paths, silent_output, seconds_per_slide=seconds_per_slide, transition=0.2)
        self._add_music(silent_output, final_output)
        return final_output

    def _render_slide(self, path: Path, slide: dict[str, Any], index: int, total: int, background_path: Path | None = None) -> None:
        palette = self._palette(str(slide.get("emotion", "")), index)
        is_end_card = self._is_end_card(slide, index, total)
        image = Image.new("RGB", (self.width, self.height), "#090909") if is_end_card else self._base_image(background_path, palette)
        draw = ImageDraw.Draw(image)

        if is_end_card:
            self._draw_end_card(image, draw, palette, slide, index, total)
            image.save(path)
            return

        self._draw_background(draw, palette, index, has_photo=background_path is not None)
        self._draw_header(draw, palette, index, total)
        if background_path is None:
            self._draw_story_visual(draw, palette, str(slide.get("role", "")), str(slide.get("emotion", "")))
        self._paste_center_logo(image)
        self._draw_text(draw, palette, slide, index)
        self._paste_logo(image, index)

        image.save(path)

    def _is_end_card(self, slide: dict[str, Any], index: int, total: int) -> bool:
        tag = str(slide.get("tag") or slide.get("role") or "").upper()
        role = str(slide.get("role") or "").lower()
        return index == total or tag == "CTA" or role == "cta"

    def _render_video_scene(self, slide_path: Path, output_path: Path, duration: int) -> None:
        frames = duration * 30
        filtergraph = (
            "scale=1080:1920,"
            f"zoompan=z='min(zoom+0.0005,1.045)':d={frames}:"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
            "format=yuv420p"
        )
        self._run_ffmpeg(
            [
                self._ffmpeg_binary(),
                "-y",
                "-loop",
                "1",
                "-i",
                str(slide_path),
                "-t",
                str(duration),
                "-vf",
                filtergraph,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )

    def _concat_scenes(self, scene_paths: list[Path], output_path: Path) -> None:
        concat_path = output_path.parent / "video-concat.txt"
        concat_path.write_text(
            "\n".join(f"file '{path.resolve().as_posix()}'" for path in scene_paths),
            encoding="utf-8",
        )
        self._run_ffmpeg(
            [
                self._ffmpeg_binary(),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                str(output_path),
            ]
        )

    def _crossfade_scenes(self, scene_paths: list[Path], output_path: Path, seconds_per_slide: int, transition: float) -> None:
        if len(scene_paths) == 1:
            shutil.copyfile(scene_paths[0], output_path)
            return
        command = [self._ffmpeg_binary(), "-y"]
        for path in scene_paths:
            command.extend(["-i", str(path)])
        filters = []
        previous = "[0:v]"
        for index in range(1, len(scene_paths)):
            output_label = f"[v{index}]"
            offset = (seconds_per_slide - transition) * index
            filters.append(
                f"{previous}[{index}:v]xfade=transition=fade:duration={transition}:offset={offset:.2f}{output_label}"
            )
            previous = output_label
        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                previous,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        try:
            self._run_ffmpeg(command)
        except RuntimeError as exc:
            if "No such filter: 'xfade'" not in str(exc):
                raise
            self._concat_scenes(scene_paths, output_path)

    def _add_music(self, video_path: Path, output_path: Path) -> None:
        music_path = self._pick_music()
        if music_path:
            music_offset = randint(8, 55)
            command = [
                self._ffmpeg_binary(),
                "-y",
                "-i",
                str(video_path),
                "-stream_loop",
                "-1",
                "-ss",
                str(music_offset),
                "-i",
                str(music_path),
                "-filter_complex",
                f"[1:a]volume={self.settings.background_music_volume},afade=t=out:st=19.4:d=1[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        elif self.settings.enable_generated_music:
            command = [
                self._ffmpeg_binary(),
                "-y",
                "-i",
                str(video_path),
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=176:sample_rate=44100",
                "-filter_complex",
                "[1:a]volume=0.06,afade=t=in:st=0:d=0.3,afade=t=out:st=19.4:d=1[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        else:
            shutil.copyfile(video_path, output_path)
            return
        self._run_ffmpeg(command)

    def _pick_music(self) -> Path | None:
        if not self.settings.enable_background_music:
            return None
        candidates: list[Path] = []
        for pattern in ("*.mp3", "*.wav", "*.m4a", "*.aac"):
            candidates.extend(self.settings.music_dir.glob(pattern))
        candidates = [path for path in candidates if path.name != ".gitkeep"]
        return choice(candidates) if candidates else None

    def _ffmpeg_binary(self) -> str:
        configured = self.settings.ffmpeg_binary
        if Path(configured).exists() or shutil.which(configured):
            return configured
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise RuntimeError("FFmpeg is not installed and bundled imageio-ffmpeg is unavailable.") from exc

    def _run_ffmpeg(self, command: list[str]) -> None:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {completed.stderr}")

    def _base_image(self, background_path: Path | None, palette: dict[str, str]) -> Image.Image:
        if not background_path:
            return Image.new("RGB", (self.width, self.height), palette["bg"])

        bg = Image.open(background_path).convert("RGB")
        bg_ratio = bg.width / bg.height
        target_ratio = self.width / self.height
        if bg_ratio > target_ratio:
            new_height = self.height
            new_width = int(new_height * bg_ratio)
        else:
            new_width = self.width
            new_height = int(new_width / bg_ratio)
        bg = bg.resize((new_width, new_height), Image.Resampling.LANCZOS)
        left = (new_width - self.width) // 2
        top = (new_height - self.height) // 2
        bg = bg.crop((left, top, left + self.width, top + self.height))
        overlay = Image.new("RGB", (self.width, self.height), "#050505")
        bg = Image.blend(bg, overlay, 0.68)
        vignette = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        vdraw = ImageDraw.Draw(vignette)
        vdraw.rectangle((0, 0, self.width, 260), fill=(0, 0, 0, 115))
        vdraw.rectangle((0, 1000, self.width, self.height), fill=(0, 0, 0, 118))
        return Image.alpha_composite(bg.convert("RGBA"), vignette).convert("RGB")

    def _draw_background(self, draw: ImageDraw.ImageDraw, palette: dict[str, str], index: int, has_photo: bool = False) -> None:
        if has_photo:
            draw.rounded_rectangle((50, 280, 1030, 1760), radius=42, outline=palette["line"], width=2)
            return
        for y in range(self.height):
            ratio = y / self.height
            r1, g1, b1 = self._hex_to_rgb(palette["bg"])
            r2, g2, b2 = self._hex_to_rgb(palette["bg2"])
            color = (
                int(r1 + (r2 - r1) * ratio),
                int(g1 + (g2 - g1) * ratio),
                int(b1 + (b2 - b1) * ratio),
            )
            draw.line((0, y, self.width, y), fill=color)

        draw.rectangle((0, 0, self.width, self.height), outline=palette["line"], width=0)
        draw.rounded_rectangle((760, 135, 1180, 560), radius=64, outline=palette["accent"], width=4)
        draw.rounded_rectangle((-180, 900, 330, 1320), radius=80, outline=palette["muted"], width=4)
        if index % 2 == 0:
            draw.rounded_rectangle((82, 216, 998, 1186), radius=34, outline=palette["line"], width=3)

    def _draw_header(self, draw: ImageDraw.ImageDraw, palette: dict[str, str], index: int, total: int) -> None:
        brand_font = self._font(42, bold=True)
        small_font = self._font(26, bold=False)
        text_x = 174 if self.logo else 72
        draw.text((text_x, 54), "ServiZephyr", fill="#D4AF37", font=brand_font)
        draw.text((text_x, 108), "Business, Customer & Control - All Yours", fill=palette["muted_text"], font=small_font)
        badge = f"{index}/{total}"
        badge_font = self._font(28, bold=True)
        badge_width = draw.textlength(badge, font=badge_font)
        draw.rounded_rectangle((self.width - 150, 56, self.width - 72, 108), radius=20, fill=palette["badge"])
        draw.text((self.width - 111 - badge_width / 2, 67), badge, fill=palette["badge_text"], font=badge_font)
        draw.rounded_rectangle((72, 154, 360, 164), radius=5, fill=palette["accent"])

    def _draw_end_card(self, image: Image.Image, draw: ImageDraw.ImageDraw, palette: dict[str, str], slide: dict[str, Any], index: int, total: int) -> None:
        for y in range(self.height):
            ratio = y / self.height
            r = int(8 + 18 * ratio)
            g = int(8 + 12 * ratio)
            b = int(8 + 4 * ratio)
            draw.line((0, y, self.width, y), fill=(r, g, b))
        draw.rounded_rectangle((86, 86, self.width - 86, self.height - 86), radius=46, outline="#D4AF37", width=4)
        draw.rounded_rectangle((self.width - 160, 56, self.width - 70, 112), radius=22, fill="#D4AF37")
        draw.text((self.width - 133, 70), f"{index}/{total}", fill="#111111", font=self._font(28, bold=True))

        if self.logo:
            logo = self.logo.resize((340, 340), Image.Resampling.LANCZOS)
            image.paste(logo, ((self.width - 340) // 2, 330), logo)

        headline = str(slide.get("headline") or "DM 'RESTAURANT' Now!")
        body = str(slide.get("body") or "Visit https://www.servizephyr.com or message us to bring control into one place.")
        title_font = self._font(72, bold=True)
        body_font = self._font(40, bold=False)
        small_font = self._font(30, bold=False)

        y = 760
        for line in self._wrap("ServiZephyr", 22)[:2]:
            width = draw.textlength(line, font=title_font)
            self._shadow_text(draw, (int((self.width - width) / 2), y), line, title_font, "#FFFFFF")
            y += 84

        y += 40
        for line in self._wrap("Business, Customer & Control - All Yours", 32)[:2]:
            width = draw.textlength(line, font=body_font)
            self._shadow_text(draw, (int((self.width - width) / 2), y), line, body_font, "#D4AF37")
            y += 56

        y = 1130
        for line in self._wrap(headline, 24)[:2]:
            width = draw.textlength(line, font=title_font)
            self._shadow_text(draw, (int((self.width - width) / 2), y), line, title_font, "#FFFFFF")
            y += 84

        y += 28
        for line in self._wrap(body, 36)[:4]:
            width = draw.textlength(line, font=body_font)
            self._shadow_text(draw, (int((self.width - width) / 2), y), line, body_font, "#E0E0E0")
            y += 54

        website = "https://www.servizephyr.com"
        website_width = draw.textlength(website, font=small_font)
        draw.text((int((self.width - website_width) / 2), 1595), website, fill="#E0E0E0", font=small_font)

    def _paste_logo(self, image: Image.Image, index: int) -> None:
        if not self.logo:
            return
        size = 86 if index != 7 else 92
        logo = self.logo.resize((size, size), Image.Resampling.LANCZOS)
        x = 72
        y = 38
        image.paste(logo, (x, y), logo)
        if index == 7:
            large = self.logo.resize((180, 180), Image.Resampling.LANCZOS)
            image.paste(large, ((self.width - 180) // 2, 250), large)

    def _paste_center_logo(self, image: Image.Image) -> None:
        if not self.logo:
            return
        logo = self.logo.resize((210, 210), Image.Resampling.LANCZOS)
        alpha = logo.getchannel("A").point(lambda value: int(value * 0.18))
        logo.putalpha(alpha)
        image.paste(logo, ((self.width - 210) // 2, 760), logo)

    def _draw_story_visual(self, draw: ImageDraw.ImageDraw, palette: dict[str, str], role: str, emotion: str) -> None:
        role = role.lower()
        emotion = emotion.lower()
        center_x = self.width // 2
        visual_top = 260

        if role in {"hook", "setup", "conflict"} or emotion in {"confusion", "frustration", "stress"}:
            self._draw_restaurant_counter(draw, palette, visual_top)
            self._draw_people(draw, palette, visual_top + 92, stressed=True)
        elif role in {"solution", "benefit"} or emotion in {"relief", "control"}:
            self._draw_dashboard(draw, palette, visual_top)
        else:
            draw.rounded_rectangle((235, visual_top, 845, visual_top + 330), radius=36, fill=palette["panel"])
            draw.ellipse((center_x - 90, visual_top + 76, center_x + 90, visual_top + 256), fill=palette["accent"])
            draw.text((center_x - 46, visual_top + 126), "SZ", fill=palette["badge_text"], font=self._font(58, bold=True))

    def _draw_restaurant_counter(self, draw: ImageDraw.ImageDraw, palette: dict[str, str], y: int) -> None:
        draw.rounded_rectangle((150, y + 220, 930, y + 355), radius=24, fill=palette["panel"])
        draw.rectangle((180, y + 250, 900, y + 280), fill=palette["line"])
        for x in (240, 390, 540, 690):
            draw.rounded_rectangle((x, y + 80, x + 94, y + 170), radius=16, fill=palette["card"])
            draw.line((x + 18, y + 112, x + 76, y + 112), fill=palette["muted_text"], width=5)
            draw.line((x + 18, y + 136, x + 62, y + 136), fill=palette["muted_text"], width=5)

    def _draw_people(self, draw: ImageDraw.ImageDraw, palette: dict[str, str], y: int, stressed: bool) -> None:
        positions = [(230, y), (430, y - 24), (620, y), (790, y - 12)]
        for i, (x, top) in enumerate(positions):
            draw.ellipse((x, top, x + 70, top + 70), fill=palette["person"])
            draw.rounded_rectangle((x - 18, top + 80, x + 88, top + 210), radius=30, fill=palette["person_body"])
            mouth_y = top + 46
            if stressed and i in {1, 2}:
                draw.arc((x + 22, mouth_y - 4, x + 48, mouth_y + 20), 180, 360, fill=palette["bg"], width=3)
                draw.text((x + 72, top - 18), "!", fill=palette["accent"], font=self._font(44, bold=True))
            else:
                draw.arc((x + 20, mouth_y - 12, x + 50, mouth_y + 16), 0, 180, fill=palette["bg"], width=3)

    def _draw_dashboard(self, draw: ImageDraw.ImageDraw, palette: dict[str, str], y: int) -> None:
        draw.rounded_rectangle((142, y, 938, y + 390), radius=34, fill=palette["panel"])
        draw.rounded_rectangle((180, y + 36, 900, y + 86), radius=18, fill=palette["card"])
        labels = ["Orders", "Billing", "Waiting", "Staff"]
        for i, label in enumerate(labels):
            x = 180 + (i % 2) * 365
            row_y = y + 126 + (i // 2) * 112
            draw.rounded_rectangle((x, row_y, x + 310, row_y + 82), radius=20, fill=palette["card"])
            draw.ellipse((x + 22, row_y + 22, x + 60, row_y + 60), fill=palette["accent"])
            draw.text((x + 78, row_y + 24), label, fill=palette["text"], font=self._font(30, bold=True))
        draw.rounded_rectangle((180, y + 326, 900, y + 344), radius=9, fill=palette["accent"])

    def _draw_text(self, draw: ImageDraw.ImageDraw, palette: dict[str, str], slide: dict[str, Any], index: int) -> None:
        headline = str(slide.get("headline") or "Restaurant Reality")
        body = str(slide.get("body") or "")

        headline_font = self._font(64, bold=True)
        body_font = self._font(40, bold=False)

        x = 100
        headline_y = 900
        body_y = 1080

        y = headline_y
        for line in self._wrap(headline, 21)[:2]:
            self._shadow_text(draw, (x, y), line, headline_font, palette["text"])
            y += 78

        y = max(body_y, y + 26)
        for line in self._wrap(body, 34)[:4]:
            self._shadow_text(draw, (x, y), line, body_font, palette["body"])
            y += 54

    def _draw_footer(self, draw: ImageDraw.ImageDraw, palette: dict[str, str]) -> None:
        return

    def _shadow_text(self, draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont, fill: str) -> None:
        x, y = xy
        draw.text((x + 3, y + 4), text, fill="#000000", font=font)
        draw.text((x, y), text, fill=fill, font=font)

    def _palette(self, emotion: str, index: int) -> dict[str, str]:
        palettes = [
            {
                "bg": "#171717",
                "bg2": "#2b1f1a",
                "text": "#fff7ed",
                "body": "#f3e8d7",
                "muted_text": "#d6c8b8",
                "accent": "#f59e0b",
                "panel": "#2f2a25",
                "card": "#3a342e",
                "line": "#5a4d42",
                "muted": "#51473d",
                "person": "#f2c7a0",
                "person_body": "#2563eb",
                "badge": "#f59e0b",
                "badge_text": "#171717",
                "footer": "#111827",
                "footer_text": "#e5e7eb",
            },
            {
                "bg": "#10231d",
                "bg2": "#142c3b",
                "text": "#f8fafc",
                "body": "#dbeafe",
                "muted_text": "#b6c7d7",
                "accent": "#22c55e",
                "panel": "#18342d",
                "card": "#21443a",
                "line": "#2e5d50",
                "muted": "#31534a",
                "person": "#e7b98f",
                "person_body": "#dc2626",
                "badge": "#22c55e",
                "badge_text": "#04130a",
                "footer": "#071b14",
                "footer_text": "#d1fae5",
            },
            {
                "bg": "#16172a",
                "bg2": "#2e1634",
                "text": "#f9fafb",
                "body": "#e9d5ff",
                "muted_text": "#c4b5fd",
                "accent": "#f97316",
                "panel": "#252846",
                "card": "#31365e",
                "line": "#4c5177",
                "muted": "#3b3f66",
                "person": "#f1bd8d",
                "person_body": "#16a34a",
                "badge": "#f97316",
                "badge_text": "#1f1307",
                "footer": "#101225",
                "footer_text": "#ede9fe",
            },
        ]
        emotion = emotion.lower()
        if emotion in {"relief", "control", "confidence"}:
            return palettes[1]
        if emotion in {"stress", "frustration", "confusion"}:
            return palettes[0]
        return palettes[(index - 1) % len(palettes)]

    def _fallback_slides(self, content: dict[str, Any]) -> list[dict[str, str]]:
        topic = content.get("topic", {})
        return [
            {
                "slide_number": 1,
                "role": "hook",
                "headline": topic.get("hook") or "Restaurant Reality",
                "body": topic.get("idea_summary") or "Peak hour me chaos fast ho jata hai.",
                "visual_direction": "restaurant rush",
                "emotion": "stress",
            }
        ]

    def _wrap(self, text: str, width: int) -> list[str]:
        return textwrap.wrap(" ".join(str(text).split()), width=width) or [str(text)]

    def _font(self, size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size=size)
        return ImageFont.load_default()

    def _hex_to_rgb(self, color: str) -> tuple[int, int, int]:
        color = color.lstrip("#")
        return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

    def _load_logo(self) -> Image.Image | None:
        if not self.settings.brand_logo_path.exists():
            return None
        logo = Image.open(self.settings.brand_logo_path).convert("RGBA")
        datas = logo.getdata()
        new_data = []
        for r, g, b, a in datas:
            if r < 10 and g < 10 and b < 10:
                new_data.append((r, g, b, 0))
            else:
                new_data.append((r, g, b, a))
        logo.putdata(new_data)
        return logo
