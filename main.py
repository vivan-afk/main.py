
import re
import uuid
from pathlib import Path
from urllib.parse import unquote
import os
import httpx
import yt_dlp
from pyrogram import Client, filters
from youtube_search import YoutubeSearch
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# API Configuration
API_URL = "https://tgmusic.fallenapi.fun"
API_KEY = "86278b_ssueajhR0D5XCET9n3HGIr0y57w2BZeR"

class DownloadResult:
    def __init__(self, success, file_path=None, error=None):
        self.success = success
        self.file_path = file_path
        self.error = error

class HttpxClient:
    def __init__(self):
        self.client = httpx.Client(timeout=30.0)

    def download_file(self, url, file_path=None, overwrite=False):
        if not url:
            return DownloadResult(success=False, error="Empty URL provided")

        headers = {"X-API-Key": API_KEY} if url.startswith(API_URL) else {}
        try:
            response = self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            if file_path is None:
                cd = response.headers.get("Content-Disposition", "")
                match = re.search(r'filename="?([^"]+)"?', cd)
                filename = unquote(match[1]) if match else (Path(url).name or uuid.uuid4().hex)
                path = Path("downloads") / filename
            else:
                path = Path(file_path)

            if path.exists() and not overwrite:
                return DownloadResult(success=True, file_path=path)

            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return DownloadResult(success=True, file_path=path)
        except httpx.HTTPError as e:
            logging.error(f"Download failed: {str(e)}")
            return DownloadResult(success=False, error=str(e))
        finally:
            if not self.client.is_closed:
                self.client.close()

    def make_request(self, url):
        if not url:
            return None
        headers = {"X-API-Key": API_KEY} if url.startswith(API_URL) else {}
        try:
            response = self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logging.error(f"Request failed: {str(e)}")
            return None
        finally:
            if not self.client.is_closed:
                self.client.close()

class YouTubeDownloader:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.http_client = HttpxClient()

    def search_and_get_url(self, query):
        try:
            results = YoutubeSearch(query, max_results=1).to_dict()
            return f"{self.base}{results[0]['id']}" if results else None
        except Exception as e:
            logging.error(f"Search error: {str(e)}")
            return None

    def download_with_api(self, video_id):
        if not video_id:
            return None
        public_url = self.http_client.make_request(f"{API_URL}/yt?id={video_id}")
        if public_url and "results" in public_url:
            dl = self.http_client.download_file(public_url["results"])
            return dl.file_path if dl.success else None
        return None

    def download(self, link, title=None):
        video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
        api_result = self.download_with_api(video_id)
        if api_result:
            return str(api_result)

        def song_audio_dl():
            fpath = f"downloads/{title or 'song'}.%(ext)s"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": fpath,
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            return f"downloads/{title or 'song'}.mp3"

        try:
            return song_audio_dl()
        except Exception as e:
            logging.error(f"Download error: {str(e)}")
            return None

# Initialize Pyrogram client
app = Client(
    name="_downloader_bot",
    api_id="12380656",
    api_hash="d927c13beaaf5110f25c505b7c071273",
    bot_token="8380016831:AAEYHdP6PTS0Gbd7v0I7b0fmu4OpIFZjykY"
)

@app.on_message(filters.command("song"))
async def download_song(client, message):
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: /song <song name>")
            return

        song_name = " ".join(message.command[1:])
        if not song_name.strip():
            await message.reply_text("Please provide a valid song name.")
            return

        await message.reply_text(f"Searching for '{song_name}'...")
        downloader = YouTubeDownloader()
        video_url = downloader.search_and_get_url(song_name)
        if not video_url:
            await message.reply_text("Could not find the song.")
            return

        await message.reply_text("Downloading the song...")
        file_path = downloader.download(video_url, song_name)
        if not file_path or not os.path.exists(file_path):
            await message.reply_text("Failed to download the song.")
            return

        await message.reply_audio(audio=file_path, caption=f"🎵 {song_name}", title=song_name)
        await message.reply_text("Song sent successfully!")
        try:
            os.remove(file_path)
            logging.info(f"Deleted file: {file_path}")
        except OSError as e:
            logging.error(f"Failed to delete file {file_path}: {str(e)}")
    except Exception as e:
        logging.error(f"Error in download_song: {str(e)}")
        await message.reply_text(f"Error: {str(e)}")

if __name__ == "__main__":
    app.run()
