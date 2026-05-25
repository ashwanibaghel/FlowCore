import asyncio
import subprocess
from pathlib import Path

from backend.app.config import Settings


class VoiceoverService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_dir = settings.uploads_dir / "voiceovers"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(self, run_id: int, text: str) -> Path | None:
        provider = self.settings.tts_provider.lower()
        if provider == "edge":
            output_path = self.output_dir / f"flowcore-voiceover-{run_id}.mp3"
            try:
                asyncio.run(self._edge_tts(text=text, output_path=output_path))
                return output_path
            except Exception:
                return self._sapi_tts(run_id=run_id, text=text)
        if provider == "sapi":
            return self._sapi_tts(run_id=run_id, text=text)
        return None

    async def _edge_tts(self, text: str, output_path: Path) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.settings.edge_tts_voice,
            rate=self.settings.edge_tts_rate,
            volume=self.settings.edge_tts_volume,
        )
        await communicate.save(str(output_path))

    def _sapi_tts(self, run_id: int, text: str) -> Path | None:
        output_path = self.output_dir / f"flowcore-voiceover-{run_id}.wav"
        text_path = self.output_dir / f"flowcore-voiceover-{run_id}.txt"
        text_path.write_text(text, encoding="utf-8")
        script = f"""
Add-Type -AssemblyName System.Speech
$text = Get-Content -LiteralPath '{text_path.resolve()}' -Raw -Encoding UTF8
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('{self.settings.sapi_tts_voice}')
$synth.Rate = {self.settings.sapi_tts_rate}
$synth.SetOutputToWaveFile('{output_path.resolve()}')
$synth.Speak($text)
$synth.Dispose()
"""
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not output_path.exists():
            return None
        return output_path
