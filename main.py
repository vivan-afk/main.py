import asyncio
import re
import uuid
from pathlib import Path
from typing import Union, Optional
from urllib.parse import unquote

import aiofiles
import httpx
import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

# API Configuration
API_URL = "https://tgmusic.fallenapi.fun"
API_KEY = "86278b_ssueajhR0D5XCET9n3HGIr0y57w2BZeR"

class DownloadResult:
    def __init__(self, success: bool, file_path: Optional[Path] = None, error: Optional[str] = None):
        self.success = success
        self.file_path = file_path
        self.error = error

class HttpxClient:
    DEFAULT_TIMEOUT = 120
    DEFAULT_DOWNLOAD_TIMEOUT = 120
    CHUNK_SIZE = 8192
    MAX_RETRIES = 2
    BACKOFF_FACTOR = 1.0

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        download_timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        max_redirects: int = 0,
    ) -> None:
        self._timeout = timeout
        self._download_timeout = download_timeout
        self._max_redirects = max_redirects
        self._session = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self._timeout,
                read=self._timeout,
                write=self._timeout,
                pool=self._timeout
            ),
            follow_redirects=max_redirects > 0,
            max_redirects=max_redirects,
        )

    async def close(self) -> None:
        try:
            await self._session.aclose()
        except Exception as e:
            print(f"Error closing HTTP session: {repr(e)}")

    async def download_file(
        self,
        url: str,
        file_path: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        **kwargs: any,
    ) -> DownloadResult:
        if not url:
            return DownloadResult(success=False, error="Empty URL provided")

        headers = kwargs.pop("headers", {})
        if API_URL and url.startswith(API_URL):
            headers["X-API-Key"] = API_KEY
        try:
            async with self._session.stream(
                "GET", url, timeout=self._download_timeout, headers=headers
            ) as response:
                response.raise_for_status()
                if file_path is None:
                    cd = response.headers.get("Content-Disposition", "")
                    match = re.search(r'filename="?([^"]+)"?', cd)
                    filename = unquote(match[1]) if match else (Path(url).name or uuid.uuid4().hex)
                    path = Path("downloads") / filename
                else:
                    path = Path(file_path) if isinstance(file_path, str) else file_path

                if path.exists() and not overwrite:
                    return DownloadResult(success=True, file_path=path)

                path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(path, "wb") as f:
                    async for chunk in response.aiter_bytes(self.CHUNK_SIZE):
                        await f.write(chunk)

                return DownloadResult(success=True, file_path=path)
        except Exception as e:
            error_msg = self._handle_http_error(e, url)
            return DownloadResult(success=False, error=error_msg)

    async def make_request(
        self,
        url: str,
        max_retries: int = MAX_RETRIES,
        backoff_factor: float = BACKOFF_FACTOR,
        **kwargs: any,
    ) -> Optional[dict]:
        if not url:
            print("Empty URL provided")
            return None

        headers = kwargs.pop("headers", {})
        if API_URL and url.startswith(API_URL):
            headers["X-API-Key"] = API_KEY
        for attempt in range(max_retries):
            try:
                response = await self._session.get(url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP error {e.response.status_code} for {url}. Body: {e.response.text}"
                print(error_msg)
                if attempt == max_retries - 1:
                    return None
            except httpx.TooManyRedirects as e:
                error_msg = f"Redirect loop for {url}: {repr(e)}"
                print(error_msg)
                if attempt == max_retries - 1:
                    return None
            except httpx.RequestError as e:
                error_msg = f"Request failed for {url}: {repr(e)}"
                print(error_msg)
                if attempt == max_retries - 1:
                    return None
            except ValueError as e:
                error_msg = f"Invalid JSON response from {url}: {repr(e)}"
                print(error_msg)
                return None
            except Exception as e:
                error_msg = f"Unexpected error for {url}: {repr(e)}"
                print(error_msg)
                return None
            await asyncio.sleep(backoff_factor * (2 ** attempt))
        print(f"All retries failed for URL: {url}")
        return None

    @staticmethod
    def _handle_http_error(e: Exception, url: str) -> str:
        if isinstance(e, httpx.TooManyRedirects):
            return f"Too many redirects for {url}: {repr(e)}"
        elif isinstance(e, httpx.HTTPStatusError):
            try:
                error_response = e.response.json()
                if isinstance(error_response, dict) and "error" in error_response:
                    return f"HTTP error {e.response.status_code} for {url}: {error_response['error']}"
            except ValueError:
                pass
            return f"HTTP error {e.response.status_code} for {url}. Body: {e.response.text}"
        elif isinstance(e, httpx.ReadTimeout):
            return f"Read timeout for {url}: {repr(e)}"
        elif isinstance(e, httpx.RequestError):
            return f"Request failed for {url}: {repr(e)}"
        return f"Unexpected error for {url}: {repr(e)}"

class YouTubeDownloader:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.http_client = HttpxClient()

    async def search_and_get_url(self, query: str) -> Optional[str]:
        try:
            results = VideosSearch(query, limit=1)
            for result in (await results.next())["result"]:
                return f"{self.base}{result['id']}"
            return None
        except Exception as e:
            print(f"Error searching YouTube: {repr(e)}")
            return None

    async def download_with_api(self, video_id: str) -> Optional[Path]:
        if not video_id:
            print("Video ID is None")
            return None

        public_url = await self.http_client.make_request(f"{API_URL}/yt?id={video_id}")
        if public_url:
            dl_url = public_url.get("results")
            if not dl_url:
                print("Response from API is empty")
                return None

            dl = await self.http_client.download_file(dl_url)
            return dl.file_path if dl.success else None
        return None

    async def download(
        self,
        link: str,
        title: Optional[str] = None,
    ) -> str:
        # Extract video ID from link
        video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link

        # Try downloading via API first
        api_result = await self.download_with_api(video_id)
        if api_result:
            return str(api_result)

        # Fallback to yt-dlp if API fails
        loop = asyncio.get_running_loop()

        def song_audio_dl():
            fpath = f"downloads/{title or 'song'}.%(ext)s"
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            return f"downloads/{title or 'song'}.mp3"

        return await loop.run_in_executor(None, song_audio_dl)

# Initialize Pyrogram client
app = Client(
    "youtube_downloader_bot",
    api_id="12380656",  # Replace with your API ID
    api_hash="d927c13beaaf5110f25c505b7c071273",  # Replace with your API Hash
    bot_token="8380016831:AAEYHdP6PTS0Gbd7v0I7b0fmu4OpIFZjykY"  # Replace with your Bot Token
)

# Bot command handler
@app.on_message(filters.command(["song", "music"]))
async def download_song(client: Client, message: Message):
    try:
        # Get the song name from the message
        if len(message.command) < 2:
            await message.reply_text("Please provide a song name. Usage: /song <song name>")
            return

        song_name = " ".join(message.command[1:])
        await message.reply_text(f"Searching for '{song_name}'...")

        # Initialize downloader
        downloader = YouTubeDownloader()

        # Search for the song
        video_url = await downloader.search_and_get_url(song_name)
        if not video_url:
            await message.reply_text("Could not find the song. Please try another name.")
            return

        # Download the song
        await message.reply_text("Downloading the song...")
        file_path = await downloader.download(video_url, song_name)

        # Send the audio file
        await message.reply_audio(
            audio=file_path,
            caption=f"🎵 {song_name}",
            title=song_name,
        )

        # Clean up the downloaded file
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {repr(e)}")

        await message.reply_text("Song sent successfully!")

    except Exception as e:
        await message.reply_text(f"An error occurred: {repr(e)}")
        print(f"Error in download_song: {repr(e)}")

# Start the bot
async def main():
    await app.start()
    print("Bot is running...")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
