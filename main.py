import asyncio
import os
import re
import uuid
import aiofiles
import httpx
import yt_dlp
from pathlib import Path
from typing import Optional, Union
from pyrogram import Client, filters
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from YukkiMusic.logging import LOGGER
from YukkiMusic.utils.database import is_on_off
from YukkiMusic.utils.formatters import time_to_seconds

# Configuration
DOWNLOADS_DIR = "downloads"
API_URL = os.getenv("API_URL", "https://tgmusic.fallenapi.fun")  # Set in environment or config
API_KEY = os.getenv("API_KEY", "739c4b_uADhloSh7dPJYQzawlxDUZ-l4zVqvY4b")  # Set in environment or config

@dataclass
class DownloadResult:
    success: bool
    file_path: Optional[Path] = None
    error: Optional[str] = None

class YouTubeAPI:
    DEFAULT_TIMEOUT = 60
    CHUNK_SIZE = 8192
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 1.0
    BASE_URL = "https://www.youtube.com/watch?v="
    REGEX = r"(?:youtube\.com|youtu\.be)"

    def __init__(self):
        self._session = httpx.AsyncClient(
            timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
            follow_redirects=True,
            max_redirects=5
        )

    async def close(self) -> None:
        try:
            await self._session.aclose()
        except Exception as e:
            LOGGER(__name__).error(f"Error closing HTTP session: {e}")

    async def download_file(self, url: str, file_path: Optional[Path] = None) -> DownloadResult:
        if not url:
            return DownloadResult(success=False, error="Empty URL provided")
        try:
            async with self._session.stream("GET", url) as response:
                response.raise_for_status()
                if file_path is None:
                    file_path = Path(DOWNLOADS_DIR) / f"{uuid.uuid4().hex}.mp4"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(file_path, "wb") as f:
                    async for chunk in response.aiter_bytes(self.CHUNK_SIZE):
                        await f.write(chunk)
                return DownloadResult(success=True, file_path=file_path)
        except Exception as e:
            error_msg = f"Download failed for {url}: {e}"
            LOGGER(__name__).error(error_msg)
            return DownloadResult(success=False, error=error_msg)

    async def download_with_api(self, video_id: str, is_video: bool = False) -> Optional[Path]:
        if not API_URL or not API_KEY:
            LOGGER(__name__).warning("API_URL or API_KEY not set")
            return None
        url = f"{API_URL}/yt?id={video_id}&video={is_video}"
        headers = {"X-API-Key": API_KEY}
        try:
            response = await self._session.get(url, headers=headers)
            response.raise_for_status()
            dl_url = response.json().get("results")
            if not dl_url:
                LOGGER(__name__).error("Empty API response")
                return None
            dl = await self.download_file(dl_url)
            return dl.file_path if dl.success else None
        except Exception as e:
            LOGGER(__name__).error(f"API download failed for {video_id}: {e}")
            return None

    async def exists(self, link: str, videoid: Optional[str] = None) -> bool:
        if videoid:
            link = self.BASE_URL + videoid
        return bool(re.search(self.REGEX, link))

    async def details(self, link: str, videoid: Optional[str] = None) -> tuple:
        if videoid:
            link = self.BASE_URL + videoid
        if "&" in link:
            link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            result = (await results.next())["result"][0]
            title = result.get("title", "Unknown Title")
            duration_min = result.get("duration", "None")
            thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
            vidid = result.get("id", "")
            duration_sec = 0 if duration_min == "None" else int(time_to_seconds(duration_min))
            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            LOGGER(__name__).error(f"Error fetching details for {link}: {e}")
            return None, None, None, None, None

    async def download(self, link: str, video: bool = False, format_id: Optional[str] = None, title: Optional[str] = None) -> tuple[str, bool]:
        if "&" in link:
            link = link.split("&")[0]
        direct = True
        loop = asyncio.get_running_loop()

        def ytdlp_download(is_video: bool) -> Optional[str]:
            ydl_opts = {
                "format": format_id or ("bestvideo[height<=720]+bestaudio/best" if is_video else "bestaudio/best"),
                "outtmpl": f"downloads/{title or '%(id)s'}.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            if not is_video:
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    file_path = f"downloads/{title or info['id']}.{'mp4' if is_video else 'mp3'}"
                    if os.path.exists(file_path):
                        return file_path
                    ydl.download([link])
                    return file_path
            except Exception as e:
                LOGGER(__name__).error(f"Error downloading {'video' if is_video else 'audio'} for {link}: {e}")
                return None

        if await is_on_off(1):  # Check if direct download is enabled
            if dl := await self.download_with_api(link.split("=")[-1], video):
                return str(dl), True
            file_path = await loop.run_in_executor(None, lambda: ytdlp_download(video))
            return file_path or "", direct
        else:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "-g",
                    "-f",
                    format_id or ("best[height<=720]" if video else "bestaudio"),
                    link,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    return stdout.decode().split("\n")[0], False
                LOGGER(__name__).error(f"Subprocess error: {stderr.decode()}")
                return "", False
            except Exception as e:
                LOGGER(__name__).error(f"Subprocess failed for {link}: {e}")
                return "", False

# Pyrogram bot implementation
app = Client("YukkiMusicBot", api_id=os.getenv("API_ID", "12380656"), api_hash=os.getenv("API_HASH", "d927c13beaaf5110f25c505b7c071273"), bot_token=os.getenv("BOT_TOKEN", "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU"))
youtube = YouTubeAPI()

@app.on_message(filters.command(["yt", "youtube"]) & filters.private)
async def youtube_download(client: Client, message: Message):
    try:
        args = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else ""
        if not args:
            await message.reply("Please provide a YouTube URL or video ID.")
            return

        video = "video" in args.lower()
        link = args.split()[0]
        if not await youtube.exists(link):
            await message.reply("Invalid YouTube URL or video ID.")
            return

        title, duration, _, thumbnail, vidid = await youtube.details(link)
        if not title:
            await message.reply("Could not fetch video details.")
            return

        await message.reply(f"Downloading: *{title}* ({duration})...")
        file_path, direct = await youtube.download(link, video=video, title=title.replace(" ", "_"))

        if not file_path:
            await message.reply("Download failed. Please try again.")
            return

        if direct:
            await message.reply_document(
                document=file_path,
                caption=f"**{title}**\nDuration: {duration}",
                thumb=thumbnail if thumbnail else None
            )
            os.remove(file_path)  # Clean up after sending
        else:
            await message.reply(f"Stream URL: {file_path}")
    except Exception as e:
        LOGGER(__name__).error(f"Error in download command: {e}")
        await message.reply("An error occurred during download.")

@app.on_disconnect()
async def on_disconnect():
    await youtube.close()

if __name__ == "__main__":
    app.run()
