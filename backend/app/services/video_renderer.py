import json
import shutil
import subprocess
import textwrap
from random import choice
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from backend.app.config import Settings
from backend.app.services.imgflip import ImgflipMemeService
from backend.app.services.media_source import PexelsMediaSource
from backend.app.services.voiceover import VoiceoverService


class VideoRenderer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_dir = settings.uploads_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render_reel(self, run_id: int, content: dict[str, Any]) -> Path:
        scenes = content["script"].get("scenes") or []
        if not scenes:
            scenes = [{"on_screen_text": content["topic"]["hook"], "visual": content["topic"]["idea_summary"]}]

        if self.settings.enable_imgflip_memes:
            meme_video = self._render_imgflip_meme_reel(run_id=run_id, content=content)
            if meme_video:
                return meme_video

        if self.settings.pexels_api_key:
            enhanced = self._render_enhanced_reel(run_id=run_id, content=content, scenes=scenes[:4])
            if enhanced:
                return enhanced

        scene_dir = self.output_dir / f"run-{run_id}-frames"
        scene_dir.mkdir(parents=True, exist_ok=True)
        frame_paths = []
        for index, scene in enumerate(scenes[:8], start=1):
            frame_path = scene_dir / f"scene-{index:02d}.png"
            self._create_scene_image(frame_path, content, scene, index, len(scenes[:8]))
            frame_paths.append(frame_path)

        concat_path = scene_dir / "concat.txt"
        lines = []
        for frame_path in frame_paths:
            lines.append(f"file '{frame_path.resolve().as_posix()}'")
            lines.append(f"duration {self.settings.video_scene_seconds}")
        lines.append(f"file '{frame_paths[-1].resolve().as_posix()}'")
        concat_path.write_text("\n".join(lines), encoding="utf-8")

        output_path = self.output_dir / f"flowcore-reel-{run_id}.mp4"
        command = [
            self._ffmpeg_binary(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vf",
            f"fps={self.settings.video_fps},format=yuv420p",
            "-c:v",
            "libx264",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"FFmpeg render failed: {completed.stderr}")
        return output_path

    def _render_imgflip_meme_reel(self, run_id: int, content: dict[str, Any]) -> Path | None:
        meme_service = ImgflipMemeService(self.settings)
        image_paths = meme_service.create_meme_story_images(run_id=run_id, content=content)
        if not image_paths:
            single_image = meme_service.create_meme_image(run_id=run_id, content=content)
            image_paths = [single_image] if single_image else []
        if not image_paths:
            return None

        voiceover_text = content["script"].get("voiceover_script") or content["script"].get("short_reel_script") or ""
        voiceover_path = (
            VoiceoverService(self.settings).synthesize(run_id=run_id, text=voiceover_text)
            if self.settings.enable_meme_voiceover and voiceover_text
            else None
        )
        scene_dir = self.output_dir / f"servizephyr-meme-reel-{run_id}-frames"
        scene_dir.mkdir(parents=True, exist_ok=True)
        scene_paths: list[Path] = []
        for index, image_path in enumerate(image_paths, start=1):
            scene_path = scene_dir / f"meme-scene-{index:02d}.mp4"
            self._render_meme_image_scene(image_path=image_path, output_path=scene_path, index=index, total=len(image_paths))
            scene_paths.append(scene_path)

        concat_path = scene_dir / "concat.txt"
        concat_path.write_text(
            "\n".join(f"file '{path.resolve().as_posix()}'" for path in scene_paths),
            encoding="utf-8",
        )
        story_output = self.output_dir / f"servizephyr-meme-reel-{run_id}-story.mp4"
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
                str(story_output),
            ]
        )
        final_output = self.output_dir / f"servizephyr-meme-reel-{run_id}.mp4"
        self._add_audio(video_path=story_output, voiceover_path=voiceover_path, output_path=final_output)
        return final_output

    def _render_meme_image_scene(self, image_path: Path, output_path: Path, index: int, total: int) -> None:
        duration = self.settings.meme_frame_seconds
        progress_width = max(1, int(self.settings.video_width * index / total))
        filtergraph = (
            f"scale={self.settings.video_width - 96}:{self.settings.video_height - 260}:force_original_aspect_ratio=decrease,"
            f"pad={self.settings.video_width}:{self.settings.video_height}:(ow-iw)/2:(oh-ih)/2:color=#111111,"
            f"zoompan=z='min(zoom+0.00045,1.035)':d={duration * self.settings.video_fps}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={self.settings.video_width}x{self.settings.video_height}:fps={self.settings.video_fps},"
            f"drawbox=x=0:y=0:w=iw:h=105:color=black@0.78:t=fill,"
            f"drawtext=text='ServiZephyr Restaurant':x=50:y=36:fontsize=34:fontcolor=white:font='Arial',"
            f"drawtext=text='Part {index}/{total}':x=w-190:y=38:fontsize=28:fontcolor=white:font='Arial',"
            f"drawbox=x=0:y=h-34:w={progress_width}:h=12:color={self.settings.video_accent_color}@0.95:t=fill,"
            f"format=yuv420p"
        )
        command = [
            self._ffmpeg_binary(),
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
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
        self._run_ffmpeg(command)

    def _render_enhanced_reel(self, run_id: int, content: dict[str, Any], scenes: list[dict[str, Any]]) -> Path | None:
        media = PexelsMediaSource(self.settings)
        clips = media.get_scene_clips(scenes=scenes, run_id=run_id)
        if not clips:
            return None

        voiceover_text = content["script"].get("voiceover_script") or content["script"].get("short_reel_script") or ""
        voiceover_path = VoiceoverService(self.settings).synthesize(run_id=run_id, text=voiceover_text) if voiceover_text else None
        scene_dir = self.output_dir / f"run-{run_id}-enhanced"
        scene_dir.mkdir(parents=True, exist_ok=True)

        rendered_scene_paths: list[Path] = []
        for index, scene in enumerate(scenes, start=1):
            source_clip = clips[(index - 1) % len(clips)]
            scene_path = scene_dir / f"scene-{index:02d}.mp4"
            self._render_video_scene(
                source_clip=source_clip,
                output_path=scene_path,
                scene=scene,
                content=content,
                scene_index=index,
                total_scenes=len(scenes),
            )
            rendered_scene_paths.append(scene_path)

        concat_path = scene_dir / "concat.txt"
        concat_path.write_text(
            "\n".join(f"file '{path.resolve().as_posix()}'" for path in rendered_scene_paths),
            encoding="utf-8",
        )
        silent_output = self.output_dir / f"flowcore-reel-{run_id}-silent.mp4"
        concat_cmd = [
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
            str(silent_output),
        ]
        self._run_ffmpeg(concat_cmd)

        final_output = self.output_dir / f"flowcore-reel-{run_id}.mp4"
        self._add_audio(
            video_path=silent_output,
            voiceover_path=voiceover_path,
            output_path=final_output,
        )
        return final_output

    def _render_video_scene(
        self,
        source_clip: Path,
        output_path: Path,
        scene: dict[str, Any],
        content: dict[str, Any],
        scene_index: int,
        total_scenes: int,
    ) -> None:
        subtitle = scene.get("on_screen_text") or scene.get("voiceover") or content["topic"].get("hook", "")
        subtitle_file = output_path.with_suffix(".srt")
        subtitle_file.write_text(self._scene_srt(subtitle), encoding="utf-8")
        style = (
            "FontName=Arial,"
            "FontSize=14,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00111111,"
            "BackColour=&H99000000,"
            "BorderStyle=4,"
            "Outline=2,"
            "Shadow=0,"
            "Alignment=2,"
            "MarginV=250"
        )
        srt_path = subtitle_file.resolve().as_posix().replace(":", "\\:").replace("'", "\\'")
        duration = str(self.settings.video_scene_seconds)
        progress_width = max(1, int(self.settings.video_width * scene_index / total_scenes))
        filtergraph = (
            f"scale={self.settings.video_width}:{self.settings.video_height}:force_original_aspect_ratio=increase,"
            f"crop={self.settings.video_width}:{self.settings.video_height},"
            f"trim=duration={duration},setpts=PTS-STARTPTS,"
            f"eq=brightness=-0.04:contrast=1.12:saturation=1.18,"
            f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.18:t=fill,"
            f"drawbox=x=70:y=118:w=270:h=8:color={self.settings.video_accent_color}@0.95:t=fill,"
            f"drawtext=text='FlowCore':x=70:y=70:fontsize=42:fontcolor=white:font='Arial':box=0,"
            f"drawbox=x=70:y=h-92:w={progress_width}:h=12:color={self.settings.video_accent_color}@0.95:t=fill,"
            f"subtitles='{srt_path}':force_style='{style}',"
            f"fps={self.settings.video_fps},format=yuv420p"
        )
        command = [
            self._ffmpeg_binary(),
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(source_clip),
            "-t",
            duration,
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
        self._run_ffmpeg(command)

    def _add_audio(self, video_path: Path, voiceover_path: Path | None, output_path: Path) -> None:
        music_path = self._pick_music()
        use_generated_music = self.settings.enable_generated_music and not music_path
        if not voiceover_path and not music_path and not use_generated_music:
            shutil.copyfile(video_path, output_path)
            return

        command = [self._ffmpeg_binary(), "-y", "-i", str(video_path)]
        filter_parts: list[str] = []
        audio_inputs: list[str] = []
        audio_index = 1

        if voiceover_path:
            command.extend(["-i", str(voiceover_path)])
            filter_parts.append(f"[{audio_index}:a]volume={self.settings.voiceover_volume}[voice]")
            audio_inputs.append("[voice]")
            audio_index += 1

        if music_path:
            command.extend(["-stream_loop", "-1", "-i", str(music_path)])
            filter_parts.append(f"[{audio_index}:a]volume={self.settings.background_music_volume}[music]")
            audio_inputs.append("[music]")
        elif use_generated_music:
            command.extend(["-f", "lavfi", "-i", "sine=frequency=176:sample_rate=44100"])
            filter_parts.append(f"[{audio_index}:a]volume=0.08,afade=t=in:st=0:d=0.25[music]")
            audio_inputs.append("[music]")

        if len(audio_inputs) == 1:
            filter_parts.append(f"{audio_inputs[0]}anull[aout]")
        else:
            filter_parts.append(f"{''.join(audio_inputs)}amix=inputs={len(audio_inputs)}:duration=first:dropout_transition=2[aout]")

        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
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
        )
        self._run_ffmpeg(command)

    def _pick_music(self) -> Path | None:
        if not self.settings.enable_background_music:
            return None
        candidates: list[Path] = []
        for pattern in ("*.mp3", "*.wav", "*.m4a", "*.aac"):
            candidates.extend(self.settings.music_dir.glob(pattern))
        return choice(candidates) if candidates else None

    def _scene_srt(self, text: str) -> str:
        lines = self._wrap(text, width=28)[:3]
        return "1\n00:00:00,250 --> 00:00:03,900\n" + "\n".join(lines) + "\n"

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

    def _create_scene_image(
        self,
        path: Path,
        content: dict[str, Any],
        scene: dict[str, Any],
        scene_index: int,
        total_scenes: int,
    ) -> None:
        width = self.settings.video_width
        height = self.settings.video_height
        bg = self.settings.video_background_color
        accent = self.settings.video_accent_color

        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image)
        title_font = self._font(78, bold=True)
        body_font = self._font(48, bold=False)
        small_font = self._font(34, bold=False)
        brand_font = self._font(38, bold=True)

        self._draw_gradient_bands(draw, width, height, accent)

        margin = 82
        draw.text((margin, 82), "FlowCore", fill="#ffffff", font=brand_font)
        draw.rounded_rectangle((margin, 152, width - margin, 164), radius=6, fill=accent)

        hook = content["topic"].get("hook", "")
        scene_text = scene.get("on_screen_text") or scene.get("voiceover") or hook
        visual = scene.get("visual", "")

        y = 430
        for line in self._wrap(scene_text, width=18)[:5]:
            draw.text((margin, y), line, fill="#ffffff", font=title_font)
            y += 94

        y += 40
        for line in self._wrap(visual, width=34)[:4]:
            draw.text((margin, y), line, fill="#d1d5db", font=body_font)
            y += 62

        cta = content["topic"].get("cta", "")
        if scene_index == total_scenes and cta:
            cta_box = (margin, height - 300, width - margin, height - 190)
            draw.rounded_rectangle(cta_box, radius=32, fill=accent)
            cta_lines = self._wrap(cta, width=26)
            cta_y = cta_box[1] + 30
            for line in cta_lines[:2]:
                text_width = draw.textlength(line, font=body_font)
                draw.text(((width - text_width) / 2, cta_y), line, fill="#06130b", font=body_font)
                cta_y += 58

        progress_width = int((width - 2 * margin) * (scene_index / total_scenes))
        draw.rounded_rectangle((margin, height - 110, width - margin, height - 92), radius=9, fill="#374151")
        draw.rounded_rectangle((margin, height - 110, margin + progress_width, height - 92), radius=9, fill=accent)
        draw.text((margin, height - 170), f"{scene_index}/{total_scenes}", fill="#9ca3af", font=small_font)

        meta = {
            "topic": content["topic"].get("reel_topic", ""),
            "scene": scene_index,
        }
        path.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=True), encoding="utf-8")
        image.save(path)

    def _draw_gradient_bands(self, draw: ImageDraw.ImageDraw, width: int, height: int, accent: str) -> None:
        for i in range(0, height, 18):
            shade = max(18, 42 - i // 70)
            color = f"#{shade:02x}{max(24, shade + 4):02x}{max(34, shade + 16):02x}"
            draw.rectangle((0, i, width, i + 18), fill=color)
        draw.rounded_rectangle((width - 360, 250, width + 180, 790), radius=80, outline=accent, width=6)
        draw.rounded_rectangle((-160, 1280, 360, 1780), radius=80, outline="#334155", width=5)

    def _wrap(self, text: str, width: int) -> list[str]:
        clean = " ".join(str(text).split())
        return textwrap.wrap(clean, width=width) or [clean]

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
