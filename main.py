import asyncio
import io
import os
import logging
import yt_dlp
import httpx
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
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

async def get_thumbnail(video_url):
    """Download and resize video thumbnail."""
    ydl_opts = {
        'skip_download': True,
        'writethumbnail': True,
        'outtmpl': 'thumbnail%(ext)s',
        'quiet': True,
        'no_warnings': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            thumbnail_path = 'thumbnail.jpg'
            if os.path.exists(thumbnail_path):
                img = Image.open(thumbnail_path).resize((320, 180), Image.LANCZOS)
                thumb_io = io.BytesIO()
                img.save(thumb_io, format='JPEG', quality=85)
                thumb_io.seek(0)
                os.remove(thumbnail_path)
                return thumb_io, info['title']
            return None, info['title']
    except Exception as e:
        logger.error(f"Thumbnail extraction failed for {video_url}: {str(e)}")
        return None, info['title'] if 'info' in locals() else "Unknown Title"

async def download_media(url, media_type):
    """Download audio or video from YouTube."""
    ydl_opts = {
        'format': 'bestaudio' if media_type == 'audio' else 'bestvideo[vcodec^=avc][height<=720]+bestaudio/best',
        'outtmpl': '%(title)s.%(ext)s',
        'merge_output_format': 'mp4' if media_type == 'video' else None,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }
        ] if media_type == 'audio' else [],
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': '/usr/bin/ffmpeg'  # Adjust if needed
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = 'mp3' if media_type == 'audio' else 'mp4'
            filename = f"{info['title']}.{ext}"
            if os.path.exists(filename):
                return filename
            return None
    except Exception as e:
        logger.error(f"Media download failed for {url} ({media_type}): {str(e)}")
        return None

async def search_song(query):
    """Search for a song using the API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                API_URL,
                params={"q": query, "api_key": API_KEY}
            )
            logger.info(f"API Response Status: {response.status_code}")
            logger.info(f"API Response Content: {response.text[:500]}")  # Truncate for brevity
            
            if response.status_code != 200:
                logger.error(f"API Error: Status code {response.status_code}")
                return []
            
            try:
                data = response.json()
                return data.get('results', [])
            except ValueError as e:
                logger.error(f"JSON Decode Error: {str(e)} - Response content: {response.text[:500]}")
                return []
    except httpx.HTTPError as e:
        logger.error(f"HTTP Error during search: {str(e)}")
        return []

@app.on_message(filters.command("song") & filters.private)
async def song_command(client, message):
    """Handle /song command to search or process YouTube URL."""
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not query:
        await message.reply("Please provide a song name or YouTube URL.", parse_mode=enums.ParseMode.MARKDOWN)
        return

    is_url = query.startswith(('https://www.youtube.com', 'https://youtu.be'))
    if is_url:
        video_url = query
    else:
        results = await search_song(query)
        if not results:
            await message.reply("No results found.", parse_mode=enums.ParseMode.MARKDOWN)
            return
        video_url = results[0].get('url')
        if not video_url:
            await message.reply("No valid URL found in search results.", parse_mode=enums.ParseMode.MARKDOWN)
            return

    thumbnail, title = await get_thumbnail(video_url)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Audio", callback_data=f"audio_{video_url}"),
            InlineKeyboardButton("Video", callback_data=f"video_{video_url}")
        ],
        [InlineKeyboardButton("Close", callback_data="close")]
    ])
    try:
        if thumbnail:
            await message.reply_photo(
                photo=thumbnail,
                caption=f"**{title}**\nChoose download format:",
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await message.reply(
                text=f"**{title}**\nChoose download format:",
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Error sending reply: {str(e)}")
        await message.reply("Error processing the request.", parse_mode=enums.ParseMode.MARKDOWN)

@app.on_callback_query()
async def handle_callback(client, callback_query):
    """Handle button callbacks for audio/video download or close."""
    data = callback_query.data
    if data == "close":
        try:
            await callback_query.message.delete()
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")
        return

    media_type, url = data.split('_', 1)
    try:
        await callback_query.message.edit_text(
            f"Downloading {media_type}...",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        filename = await download_media(url, media_type)
        if not filename:
            await callback_query.message.edit_text(
                f"Failed to download {media_type}.",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        with open(filename, 'rb') as file:
            if media_type == 'audio':
                await callback_query.message.reply_audio(
                    audio=file,
                    caption=filename,
                    parse_mode=enums.ParseMode.MARKDOWN
                )
            else:
                await callback_query.message.reply_video(
                    video=file,
                    caption=filename,
                    parse_mode=enums.ParseMode.MARKDOWN
                )
        os.remove(filename)
    except Exception as e:
        logger.error(f"Error processing callback ({media_type}): {str(e)}")
        await callback_query.message.edit_text(
            f"Error downloading {media_type}: {str(e)}",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    finally:
        try:
            await callback_query.message.delete()
        except Exception as e:
            logger.error(f"Error deleting message after download: {str(e)}")

if __name__ == "__main__":
    app.run()
