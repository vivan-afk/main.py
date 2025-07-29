import asyncio
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
import os
import json
from bs4 import BeautifulSoup
import logging

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

async def download_song(song_name: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
            logger.info(f"Searching for song: {song_name}")
            response = await client.get(
                API_URL,
                headers=headers,
                params={"query": song_name}
            )
            response.raise_for_status()
            html_content = response.text
            logger.debug(f"Received HTML response: {html_content[:500]}...")  # Log first 500 chars for debugging

            # Try to extract JSON from HTML
            try:
                json_start = html_content.find('{')
                json_end = html_content.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = html_content[json_start:json_end]
                    data = json.loads(json_str)
                    download_url = data.get('download_url')
                    if not download_url:
                        logger.error("No 'download_url' found in JSON data")
                        return None
                else:
                    logger.warning("No JSON object found in HTML response")
                    download_url = None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from HTML response: {e}")
                download_url = None

            # Fallback to BeautifulSoup for parsing HTML
            if not download_url:
                logger.info("Falling back to BeautifulSoup for HTML parsing")
                soup = BeautifulSoup(html_content, 'html.parser')
                audio_tag = soup.find('a', href=lambda href: href and '.mp3' in href.lower())
                if audio_tag and audio_tag['href']:
                    download_url = audio_tag['href']
                    logger.info(f"Found download URL in HTML: {download_url}")
                else:
                    logger.error("No .mp3 link found in HTML response")
                    return None

            # Ensure the URL is absolute
            if not download_url.startswith(('http://', 'https://')):
                from urllib.parse import urljoin
                download_url = urljoin(API_URL, download_url)
                logger.info(f"Converted to absolute URL: {download_url}")

            # Download the audio file
            logger.info(f"Downloading audio from: {download_url}")
            audio_response = await client.get(download_url)
            audio_response.raise_for_status()

            content_type = audio_response.headers.get("content-type", "")
            if "audio/mpeg" not in content_type.lower():
                logger.error(f"Invalid content type received: {content_type}")
                return None

            output_file = f"downloads/{song_name.replace('/', '_')}.mp3"  # Sanitize filename
            os.makedirs("downloads", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(audio_response.content)

            # Verify file is not empty
            if os.path.getsize(output_file) == 0:
                logger.error("Downloaded file is empty")
                os.remove(output_file)
                return None

            logger.info(f"Successfully downloaded song to: {output_file}")
            return output_file

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading song: {e}")
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
        status_msg = await message.reply_text("🔍 Searching for your song...")
        file_path = await download_song(song_name)
        if not file_path:
            await status_msg.edit_text("❌ Failed to download the song. Please try again!")
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
