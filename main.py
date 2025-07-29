import asyncio
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
import os
import json
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin
import yt_dlp
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "8380016831:AAEYHdP6PTS0Gbd7v0I7b0fmu4OpIFZjykY"
API_KEY = "86278b_ssueajhR0D5XCET9n3HGIr0y57w2BZeR"
API_URL = "https://tgmusic.fallenapi.fun"

app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

def extract_json_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and '{' in script.string:
            try:
                json_matches = re.findall(r'\{.*?\}', script.string, re.DOTALL)
                for json_str in json_matches:
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, dict) and any(key in data for key in ['download_url', 'url', 'audio_url']):
                            return data
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                logger.debug(f"Error processing script tag: {e}")
    return None

async def download_song(song_name: str) -> str:
    # Try primary API first
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
            logger.info(f"Searching for song via API: {song_name}")
            response = await client.get(
                API_URL,
                headers=headers,
                params={"query": song_name}
            )
            response.raise_for_status()
            html_content = response.text
            logger.info(f"Response headers: {response.headers}")
            logger.info(f"HTML response snippet (first 500 chars): {html_content[:500]}")

            # Save HTML response for debugging
            debug_file = f"debug/response_{song_name.replace('/', '_')}.html"
            os.makedirs("debug", exist_ok=True)
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Saved HTML response to: {debug_file}")

            # Try to extract JSON from HTML
            download_url = None
            data = extract_json_from_html(html_content)
            if data:
                download_url = data.get('download_url') or data.get('url') or data.get('audio_url')
                if download_url:
                    logger.info(f"Found download URL in JSON: {download_url}")
                else:
                    logger.warning("No download URL found in JSON data")

            # Fallback to BeautifulSoup for parsing HTML
            if not download_url:
                logger.info("Falling back to BeautifulSoup for HTML parsing")
                soup = BeautifulSoup(html_content, 'html.parser')
                audio_extensions = ('.mp3', '.m4a', '.wav', '.ogg', '.flac')
                # Check <a> tags
                audio_tag = soup.find('a', href=lambda href: href and any(ext in href.lower() for ext in audio_extensions))
                if audio_tag and audio_tag['href']:
                    download_url = audio_tag['href']
                    logger.info(f"Found audio link in HTML: {download_url}")
                else:
                    # Check <audio> tags
                    audio_element = soup.find('audio')
                    if audio_element and audio_element.get('src'):
                        download_url = audio_element['src']
                        logger.info(f"Found audio src in HTML: {download_url}")
                    else:
                        logger.warning("No audio link found in HTML response. Falling back to YouTube.")

            # If download URL found, download from API
            if download_url:
                # Ensure the URL is absolute
                if not download_url.startswith(('http://', 'https://')):
                    download_url = urljoin(API_URL, download_url)
                    logger.info(f"Converted to absolute URL: {download_url}")

                logger.info(f"Downloading audio from API: {download_url}")
                audio_response = await client.get(download_url)
                audio_response.raise_for_status()

                content_type = audio_response.headers.get("content-type", "").lower()
                if not any(audio_type in content_type for audio_type in ("audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg", "audio/flac")):
                    logger.error(f"Invalid content type received: {content_type}")
                    return None

                output_file = f"downloads/{song_name.replace('/', '_')}.mp3"
                os.makedirs("downloads", exist_ok=True)
                with open(output_file, "wb") as f:
                    f.write(audio_response.content)

                # Verify file is not empty
                if os.path.getsize(output_file) == 0:
                    logger.error("Downloaded file is empty")
                    os.remove(output_file)
                    return None

                logger.info(f"Successfully downloaded song from API to: {output_file}")
                return output_file

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred with API: {e}")
    except Exception as e:
        logger.error(f"Unexpected error downloading song from API: {e}")

    # Fallback to YouTube using yt-dlp
    logger.info(f"Falling back to YouTube for song: {song_name}")
    try:
        output_file = f"downloads/{song_name.replace('/', '_')}.mp3"
        os.makedirs("downloads", exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_file,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',  # Automatically search YouTube
            'noplaylist': True,  # Download only the first video
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([song_name])

        # Verify file exists and is not empty
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            logger.error("YouTube download failed or file is empty")
            if os.path.exists(output_file):
                os.remove(output_file)
            return None

        logger.info(f"Successfully downloaded song from YouTube to: {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"Error downloading from YouTube: {e}")
        return None

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Hi! I'm a Music Bot.\n"
        "Use /song <song name> to download songs.\n"
        "Example: /song sanam re"
    )

@app.on_message(filters.command("song"))
async def song_command(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("❌ Please provide a song name!\nExample: /song sanam re")
            return
        song_name = " ".join(message.command[1:])
        if len(song_name) < 3:
            await message.reply_text("❌ Song name is too short! Please provide a valid song name.")
            return
        status_msg = await message.reply_text("🔍 Searching for your song...")
        file_path = await download_song(song_name)
        if not file_path:
            await status_msg.edit_text("❌ Failed to download the song from both API and YouTube. Please try a different song or check the spelling!")
            return
        await status_msg.edit_text("📤 Uploading your song...")
        await message.reply_audio(
            audio=file_path,
            caption=f"🎵 {song_name}\n\nRequested by: {message.from_user.mention}",
        )
        await status_msg.delete()
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up downloaded file: {file_path}")
    except Exception as e:
        logger.error(f"Error in song command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")

if __name__ == "__main__":
    logger.info("Starting MusicBot...")
    app.run()
