import asyncio, io, os, yt_dlp, httpx
from pyrogram import filters, enums, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image

# Replace these with your own values
API_ID = 12380656  # your api_id (integer)
API_HASH = "d927c13beaaf5110f25c505b7c071273"  # your api_hash (string)
BOT_TOKEN = "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU"  # only for bots, comment out if userbot
API_URL = "https://tgmusic.fallenapi.fun" # yt api url for correct endpoints
API_KEY = "a054ac_9-knP8fv5euZAT9sfA5uCVYVABKU1kUp" # yt api key for bypass yt restrictions

app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

async def get_thumbnail(video_url):
    ydl_opts = {'skip_download': True, 'writethumbnail': True, 'outtmpl': 'thumbnail%(ext)s'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        thumbnail_path = 'thumbnail.jpg'
        if os.path.exists(thumbnail_path):
            img = Image.open(thumbnail_path).resize((320, 180), Image.LANCZOS)
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG')
            thumb_io.seek(0)
            os.remove(thumbnail_path)
            return thumb_io, info['title']
        return None, info['title']

async def download_media(url, media_type):
    ydl_opts = {
        'format': 'bestaudio' if media_type == 'audio' else 'bestvideo+bestaudio/best',
        'outtmpl': f'%(title)s.{media_type}',
        'merge_output_format': 'mp4' if media_type == 'video' else None,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}] if media_type == 'audio' else []
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return f"{info['title']}.{'mp3' if media_type == 'audio' else 'mp4'}"

async def search_song(query):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_URL}", params={"q": query, "api_key": API_KEY})
        return response.json().get('results', []) if response.status_code == 200 else []

@app.on_message(filters.command("song") & filters.private)
async def song_command(client, message):
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not query:
        await message.reply("Please provide a song name or YouTube URL.", parse_mode=enums.ParseMode.MARKDOWN)
        return
    is_url = query.startswith(('https://www.youtube.com', 'https://youtu.be'))
    video_url = query if is_url else (await search_song(query))[0].get('url') if (await search_song(query)) else None
    if not video_url:
        await message.reply("No results found.", parse_mode=enums.ParseMode.MARKDOWN)
        return
    thumbnail, title = await get_thumbnail(video_url)
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Audio", callback_data=f"audio_{video_url}"), InlineKeyboardButton("Video", callback_data=f"video_{video_url}")],
        [InlineKeyboardButton("Close", callback_data="close")]
    ])
    if thumbnail:
        await message.reply_photo(photo=thumbnail, caption=f"{title}\nChoose download format:", reply_markup=buttons, parse_mode=enums.ParseMode.MARKDOWN)
    else:
        await message.reply(text=f"{title}\nChoose download format:", reply_markup=buttons, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    if data == "close":
        await callback_query.message.delete()
        return
    media_type, url = data.split('_', 1)
    await callback_query.message.edit_text(f"Downloading {media_type}...", parse_mode=enums.ParseMode.MARKDOWN)
    try:
        filename = await download_media(url, media_type)
        with open(filename, 'rb') as file:
            if media_type == 'audio':
                await callback_query.message.reply_audio(audio=file, caption=filename, parse_mode=enums.ParseMode.MARKDOWN)
            else:
                await callback_query.message.reply_video(video=file, caption=filename, parse_mode=enums.ParseMode.MARKDOWN)
        os.remove(filename)
    except Exception as e:
        await callback_query.message.edit_text(f"Error downloading {media_type}: {str(e)}", parse_mode=enums.ParseMode.MARKDOWN)
    finally:
        await callback_query.message.delete()


if __name__ == "__main__":
    app.run()
