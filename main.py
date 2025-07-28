import httpx
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
from urllib.parse import urlparse, parse_qs

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_ID = 12380656
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU"
API_URL = "https://tgmusic.fallenapi.fun"
API_KEY = "a054ac_9-knP8fv5euZAT9sfA5uCVYVABKU1kUp"

# Initialize Pyrogram client
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def fetch_download_url(query: str, is_audio: bool) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                API_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                params={"query": query, "type": "audio" if is_audio else "video"}
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                logger.error(f"Unexpected content type: {content_type}, response: {response.text}")
                return {"error": "Invalid response format"}
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}, status: {e.response.status_code}, response: {e.response.text}")
            return {"error": f"HTTP error: {e}"}
        except Exception as e:
            logger.error(f"API error: {e}")
            return {"error": str(e)}

async def download_file(url: str, filename: str) -> bool:
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(filename, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
                return True
        except Exception as e:
            logger.error(f"Download error: {e}")
            if os.path.exists(filename):
                os.remove(filename)
            return False

def parse_youtube_url(url: str) -> str:
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    if "youtube.com" in parsed.hostname or parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/") if parsed.hostname == "youtu.be" else parse_qs(parsed.query).get("v", [url])[0]
    return url

async def process_query(query: str, is_audio: bool) -> tuple:
    os.makedirs("downloads", exist_ok=True)
    query = parse_youtube_url(query) if ("youtube.com" in query or "youtu.be" in query) else query
    
    data = await fetch_download_url(query, is_audio)
    if "error" in data or not data.get("url"):
        return None, data.get("error", "No download URL found")
    
    title = "".join(c for c in data.get("title", "file") if c.isalnum() or c in " _-")[:50]
    ext = "mp3" if is_audio else "mp4"
    filename = f"downloads/{title}.{ext}"
    
    return (filename, None) if await download_file(data["url"], filename) else (None, "Download failed")

@app.on_message(filters.command(["start"]))
async def start_command(client, message):
    await message.reply_text("Send a YouTube URL or search query to download.")

@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_text(client, message):
    query = message.text.strip()
    if not query:
        await message.reply_text("Please provide a valid query.")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Video", callback_data=f"video_{query}")],
        [InlineKeyboardButton("Audio", callback_data=f"audio_{query}")]
    ])
    await message.reply_text("Choose format:", reply_markup=keyboard)

@app.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    is_audio = data.startswith("audio_")
    query = data.replace("audio_", "").replace("video_", "")
    
    await callback_query.message.edit_text("Processing...")
    
    filename, error = await process_query(query, is_audio)
    if error:
        await callback_query.message.edit_text(f"Error: {error}")
        return
    
    file_size = os.path.getsize(filename) / (1024 * 1024)
    if file_size > 50:
        await callback_query.message.edit_text("File too large (>50MB).")
        os.remove(filename)
        return
    
    try:
        with open(filename, "rb") as f:
            if is_audio:
                await callback_query.message.reply_audio(audio=f, caption=os.path.basename(filename))
            else:
                await callback_query.message.reply_video(video=f, caption=os.path.basename(filename))
    finally:
        await callback_query.message.delete()
        os.remove(filename)

if __name__ == "__main__":
    app.run()
