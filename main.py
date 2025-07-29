
import re
import uuid
import hashlib
from pathlib import Path
from urllib.parse import unquote
import os
import httpx
import yt_dlp
from pyrogram import Client, filters
from youtube_search import YoutubeSearch
import logging
import time
import backoff
import asyncio
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# API Configuration
API_URL = "https://tgmusic.fallenapi.fun"
API_KEY = "86278b_ssueajhR0D5XCET9n3HGIr0y57w2BZeR"
CACHE_DIR = Path("cache")
CACHE_EXPIRY = timedelta(hours=24)  # Cache files for 24 hours

class DownloadResult:
    def __init__(self, success, file_path=None, error=None, metadata=None):
        self.success = success
        self.file_path = file_path
        self.error = error
        self.metadata = metadata or {}

class AsyncHttpxClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    @backoff.on_exception(backoff.expo, httpx.HTTPError, max_tries=3)
    async def download_file(self, url, file_path=None, overwrite=False):
        if not url:
            return DownloadResult(success=False, error="Empty URL provided")

        headers = {"X-API-Key": API_KEY} if url.startswith(API_URL) else {}
        try:
            # Make a HEAD request to check Content-Type and Content-Length
            head_response = await self.client.head(url, headers=headers, follow_redirects=True)
            head_response.raise_for_status()

            content_type = head_response.headers.get("Content-Type", "")
            content_length = int(head_response.headers.get("Content-Length", 0))
            if "audio" not in content_type and "octet-stream" not in content_type:
                logging.warning(f"Unexpected Content-Type: {content_type} for URL: {url}")
                return DownloadResult(success=False, error=f"Invalid content type: {content_type}")
            if content_length == 0:
                logging.error(f"No content body in response from {url}")
                return DownloadResult(success=False, error="Response has no downloadable content")

            # Proceed with GET request to download the file
            response = await self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()

            # Determine file path
            if file_path is None:
                cd = response.headers.get("Content-Disposition", "")
                match = re.search(r'filename="?([^"]+)"?', cd)
                filename = unquote(match.group(1)) if match and match.group(1) else f"{uuid.uuid4().hex}.mp3"
                path = Path("downloads") / filename
            else:
                path = Path(file_path)

            if path.exists() and not overwrite:
                return DownloadResult(success=True, file_path=path)

            # Save the file
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
            return DownloadResult(success=True, file_path=path)
        except httpx.HTTPError as e:
            logging.error(f"Download failed for {url}: {str(e)}")
            return DownloadResult(success=False, error=str(e))
        except Exception as e:
            logging.error(f"Unexpected error during download from {url}: {str(e)}")
            return DownloadResult(success=False, error=str(e))

    @backoff.on_exception(backoff.expo, httpx.HTTPError, max_tries=3)
    async def make_request(self, url):
        if not url:
            return None
        headers = {"X-API-Key": API_KEY} if url.startswith(API_URL) else {}
        try:
            response = await self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logging.error(f"Request failed for {url}: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in request to {url}: {str(e)}")
            return None

    async def close(self):
        if not self.client.is_closed:
            await self.client.aclose()

class YouTubeDownloader:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.http_client = AsyncHttpxClient()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.http_client.close()

    def _get_cache_key(self, query):
        """Generate a cache key based on the query."""
        return hashlib.md5(query.lower().encode()).hexdigest()

    def _check_cache(self, query):
        """Check if a cached file exists and is valid."""
        cache_key = self._get_cache_key(query)
        cache_file = CACHE_DIR / f"{cache_key}.mp3"
        metadata_file = CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists() and metadata_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < CACHE_EXPIRY:
                try:
                    with open(metadata_file, "r") as f:
                        import json
                        metadata = json.load(f)
                    return DownloadResult(success=True, file_path=cache_file, metadata=metadata)
                except Exception as e:
                    logging.error(f"Failed to read cached metadata: {str(e)}")
        return None

    def _save_to_cache(self, query, file_path, metadata):
        """Save file and metadata to cache."""
        cache_key = self._get_cache_key(query)
        cache_file = CACHE_DIR / f"{cache_key}.mp3"
        metadata_file = CACHE_DIR / f"{cache_key}.json"
        try:
            import shutil
            shutil.copy(file_path, cache_file)
            with open(metadata_file, "w") as f:
                import json
                json.dump(metadata, f)
            logging.info(f"Cached file for query: {query}")
        except Exception as e:
            logging.error(f"Failed to cache file: {str(e)}")

    async def search_and_get_url(self, query):
        try:
            # Enhance query for music-specific results
            enhanced_query = f"{query} official audio"
            results = YoutubeSearch(enhanced_query, max_results=5).to_dict()
            if not results:
                logging.info(f"No results for enhanced query, trying original: {query}")
                results = YoutubeSearch(query, max_results=5).to_dict()
            
            if not results:
                return None, {}

            # Select the best result based on title and duration
            for result in results:
                title = result.get('title', '').lower()
                duration = result.get('duration', '')
                if "audio" in title or "official" in title or "music" in title:
                    if duration and ":" in duration:
                        minutes = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration.split(":"))))
                        if 1 <= minutes <= 10:
                            metadata = {
                                "title": result.get("title", "Unknown"),
                                "artist": result.get("channel", "Unknown"),
                                "duration": duration,
                                "thumbnail": result.get("thumbnails", [None])[0]
                            }
                            return f"{self.base}{result['id']}", metadata
            # Fallback to first result
            metadata = {
                "title": results[0].get("title", "Unknown"),
                "artist": results[0].get("channel", "Unknown"),
                "duration": results[0].get("duration", "Unknown"),
                "thumbnail": results[0].get("thumbnails", [None])[0]
            }
            return f"{self.base}{results[0]['id']}", metadata
        except Exception as e:
            logging.error(f"Search error: {str(e)}")
            return None, {}

    async def download_with_api(self, video_id, query):
        if not video_id:
            return DownloadResult(success=False, error="Invalid video ID")
        public_url = await self.http_client.make_request(f"{API_URL}/yt?id={video_id}")
        if not public_url or "results" not in public_url:
            logging.error(f"API response invalid or missing 'results' for video_id {video_id}")
            return DownloadResult(success=False, error="Invalid API response")
        download_url = public_url.get("results")
        if not isinstance(download_url, str) or not download_url.startswith("http"):
            logging.warning(f"Invalid download URL in API response: {download_url}")
            return DownloadResult(success=False, error="Invalid download URL")
        
        logging.info(f"Attempting to download from API: {download_url}")
        result = await self.http_client.download_file(download_url)
        if result.success:
            result.metadata = await self._get_metadata(video_id, query)  # Fetch metadata if needed
            self._save_to_cache(query, result.file_path, result.metadata)
        return result

    async def _get_metadata(self, video_id, query):
        """Extract metadata using yt_dlp."""
        url = f"{self.base}{video_id}"
        ydl_opts = {"quiet": True, "no_warnings": True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "title": info.get("title", "Unknown"),
                    "artist": info.get("uploader", "Unknown"),
                    "album": info.get("album", "Unknown"),
                    "duration": str(timedelta(seconds=int(info.get("duration", 0)))),
                    "thumbnail": info.get("thumbnail", None)
                }
        except Exception as e:
            logging.error(f"Metadata extraction failed: {str(e)}")
            return {"title": query, "artist": "Unknown", "album": "Unknown", "duration": "Unknown"}

    async def download(self, link, title, query):
        video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link

        # Check cache first
        cached = self._check_cache(query)
        if cached:
            logging.info(f"Using cached file for query: {query}")
            return cached

        # Try API download
        api_result = await self.download_with_api(video_id, query)
        if api_result.success:
            return api_result

        # Fallback to yt_dlp
        async def song_audio_dl():
            unique_filename = f"{title or 'song'}_{uuid.uuid4().hex}.%(ext)s"
            fpath = f"downloads/{unique_filename}"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": fpath,
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",  # Set to 320 kbps
                }],
                "noplaylist": True,
                "cookiefile": "cookies.txt",  # Optional: for restricted videos
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    if info.get('is_live'):
                        raise Exception("Cannot download live streams")
                    if info.get('duration') and info['duration'] > 600:
                        raise Exception("Video is too long for a song")
                    ydl.download([link])
                file_path = f"downloads/{unique_filename % {'ext': 'mp3'}}"
                metadata = {
                    "title": info.get("title", title or "Unknown"),
                    "artist": info.get("uploader", "Unknown"),
                    "album": info.get("album", "Unknown"),
                    "duration": str(timedelta(seconds=int(info.get("duration", 0)))),
                    "thumbnail": info.get("thumbnail", None)
                }
                self._save_to_cache(query, file_path, metadata)
                return DownloadResult(success=True, file_path=file_path, metadata=metadata)
            except Exception as e:
                logging.error(f"yt_dlp download failed: {str(e)}")
                raise

        for attempt in range(3):
            try:
                logging.info(f"Falling back to yt_dlp for {link} (attempt {attempt + 1})")
                return await song_audio_dl()
            except Exception as e:
                if attempt == 2:
                    logging.error(f"Download error after retries: {str(e)}")
                    return DownloadResult(success=False, error=str(e))
                await asyncio.sleep(2 ** attempt)

# Initialize Pyrogram client
app = Client(
    name="_downloader_bot",
    api_id="12380656",
    api_hash="d927c13beaaf5110f25c505b7c071273",
    bot_token="8380016831:AAEYHdP6PTS0Gbd7v0I7b0fmu4OpIFZjykY"
)

@app.on_message(filters.command("song"))
async def download_song(client, message):
    async with YouTubeDownloader() as downloader:
        try:
            if len(message.command) < 2:
                await message.reply_text("Usage: /song <song name>")
                return

            song_name = " ".join(message.command[1:]).strip()
            if not song_name:
                await message.reply_text("Please provide a valid song name.")
                return

            await message.reply_text(f"Searching for '{song_name}'...")
            video_url, metadata = await downloader.search_and_get_url(song_name)
            if not video_url:
                await message.reply_text("Could not find the song. Try a different query.")
                return

            await message.reply_text("Downloading the song...")
            result = await downloader.download(video_url, song_name, song_name)
            if not result.success or not result.file_path or not os.path.exists(result.file_path):
                await message.reply_text(f"Failed to download the song: {result.error or 'Unknown error'}")
                return

            # Format metadata for caption
            caption = (
                f"🎵 **{result.metadata.get('title', song_name)}**\n"
                f"👤 **Artist**: {result.metadata.get('artist', 'Unknown')}\n"
                f"💿 **Album**: {result.metadata.get('album', 'Unknown')}\n"
                f"⏱ **Duration**: {result.metadata.get('duration', 'Unknown')}"
            )

            # Send audio with thumbnail if available
            if result.metadata.get("thumbnail"):
                async with httpx.AsyncClient() as client:
                    thumb_response = await client.get(result.metadata["thumbnail"])
                    thumb_path = Path("downloads") / f"{uuid.uuid4().hex}.jpg"
                    with open(thumb_path, "wb") as f:
                        f.write(thumb_response.content)
                    await message.reply_audio(
                        audio=result.file_path,
                        caption=caption,
                        title=result.metadata.get("title", song_name),
                        performer=result.metadata.get("artist", "Unknown"),
                        duration=int(sum(int(x) * 60 ** i for i, x in enumerate(reversed(result.metadata.get("duration", "0:00").split(":"))))),
                        thumb=thumb_path
                    )
                    try:
                        os.remove(thumb_path)
                    except OSError as e:
                        logging.error(f"Failed to delete thumbnail: {str(e)}")
            else:
                await message.reply_audio(
                    audio=result.file_path,
                    caption=caption,
                    title=result.metadata.get("title", song_name),
                    performer=result.metadata.get("artist", "Unknown"),
                    duration=int(sum(int(x) * 60 ** i for i, x in enumerate(reversed(result.metadata.get("duration", "0:00").split(":")))))
                )

            await message.reply_text("Song sent successfully!")
            try:
                os.remove(result.file_path)
                logging.info(f"Deleted file: {result.file_path}")
            except OSError as e:
                logging.error(f"Failed to delete file {result.file_path}: {str(e)}")
        except Exception as e:
            logging.error(f"Error in download_song: {str(e)}")
            await message.reply_text(f"Error: {str(e)}")

if __name__ == "__main__":
    app.run()
