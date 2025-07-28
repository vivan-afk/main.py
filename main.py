import httpx
import os
from urllib.parse import urlparse, parse_qs
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Replace these with environment variables in production
API_ID = 12380656  # Your api_id (integer)
API_HASH = "d927c13beaaf5110f25c505b7c071273"  # Your api_hash (string)
BOT_TOKEN = "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU"  # Bot token
API_URL = "https://tgmusic.fallenapi.fun"  # YT API URL
API_KEY = "a054ac_9-knP8fv5euZAT9sfA5uCVYVABKU1kUp"  # YT API key

# Initialize Pyrogram client
app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

async def fetch_download_url(query: str, is_audio: bool = False) -> dict:
    headers = [
        {"Authorization": f"Bearer {API_KEY}"},
        {"X-API-Key": API_KEY},
        {"api_key": API_KEY}
    ]
    params = {"query": query, "type": "audio" if is_audio else "video"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for header in headers:
            try:
                logger.info(f"Trying request with header: {list(header.keys())[0]}")
                response = await client.get(f"{API_URL}", headers=header, params=params)
                response.raise_for_status()
                
                # Log the raw response for debugging
                response_text = await response.aread()  # Read response as bytes
                logger.info(f"Raw response: {response_text.decode('utf-8', errors='ignore')}")
                
                # Check if response is empty
                if not response_text:
                    logger.error("API returned an empty response")
                    return {"error": "Empty response from API"}
                
                # Try parsing JSON
                try:
                    data = response.json()
                    logger.info("API request successful")
                    return data
                except ValueError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    return {"error": f"Invalid JSON response from API: {e}"}
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"API request failed with header {list(header.keys())[0]}: {e}")
                if e.response.status_code == 401:
                    continue  # Try next header
                return {"error": f"HTTP error: {e}"}
            except Exception as e:
                logger.error(f"Error fetching download URL: {e}")
                return {"error": f"Request error: {e}"}
        return {"error": "All authentication methods failed (401 Unauthorized)"}

async def download_file(url: str, filename: str) -> bool:
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("GET", url, timeout=60.0) as response:
                response.raise_for_status()
                with open(filename, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
            logger.info(f"Downloaded: {filename}")
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

def parse_youtube_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname in ["www.youtube.com", "youtube.com"]:
        query_params = parse_qs(parsed.query)
        return query_params.get("v", [None])[0] or parsed.path.split("/")[-1]
    elif parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/")
    return url

async def process_query(query: str, is_audio: bool = False) -> tuple:
    output_dir = "downloads"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if "youtube.com" in query or "youtu.be" in query:
        query = parse_youtube_url(query)
    
    data = await fetch_download_url(query, is_audio)
    if "error" in data:
        return None, data["error"]
    
    if not data or "url" not in data:
        return None, "No download URL found."
    
    download_url = data["url"]
    title = data.get("title", "downloaded_file")
    ext = "mp3" if is_audio else "mp4"
    filename = os.path.join(output_dir, f"{title}.{ext}".replace("/", "_").replace("\\", "_"))
    
    success = await download_file(download_url, filename)
    if success:
        return filename, None
    return None, "Failed to download the file."

@app.on_message(filters.command(["start"]))
async def start_command(client, message):
    await message.reply_text(
        "Welcome to the YouTube Downloader Bot! Send a YouTube URL or search query to download a video or audio."
    )

@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_text(client, message):
    query = message.text.strip()
    if not query:
        await message.reply_text("Please provide a valid YouTube URL or search query.")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Download Video", callback_data=f"video_{query}")],
        [InlineKeyboardButton("Download Audio", callback_data=f"audio_{query}")]
    ])
    await message.reply_text("Choose download format:", reply_markup=keyboard)

@app.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    is_audio = data.startswith("audio_")
    query = data.replace("audio_", "").replace("video_", "")
    
    await callback_query.message.edit_text("Processing your request...")
    
    filename, error = await process_query(query, is_audio)
    if error:
        await callback_query.message.edit_text(error)
        return
    
    file_size = os.path.getsize(filename) / (1024 * 1024)  # Size in MB
    if file_size > 50:  # Telegram's file size limit for bots
        await callback_query.message.edit_text("File is too large to send via Telegram (>50MB).")
        os.remove(filename)
        return
    
    with open(filename, "rb") as f:
        if is_audio:
            await callback_query.message.reply_audio(audio=f, caption="Downloaded audio")
        else:
            await callback_query.message.reply_video(video=f, caption="Downloaded video")
    
    await callback_query.message.delete()
    os.remove(filename)

if __name__ == "__main__":
    logger.info("Starting YouTube Downloader Bot...")
    app.run()
