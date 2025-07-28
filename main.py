
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message
import requests
from urllib.parse import quote

# Bot configuration
API_ID = int(os.getenv("API_ID", "12380656"))
API_HASH = os.getenv("API_HASH", "d927c13beaaf5110f25c505b7c071273")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU")
DOWNLOAD_API_URL = "https://tgmusic.fallenapi.fun"

app = Client("yt_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Start command handler
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Welcome to the YouTube Downloader Bot! 🎥\n"
        "Send me a YouTube video URL to download it.\n"
        "Example: https://www.youtube.com/watch?v=video_id"
    )

# Handle YouTube URL messages
@app.on_message(filters.text & filters.regex(r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/"))
async def handle_youtube_url(client: Client, message: Message):
    youtube_url = message.text
    chat_id = message.chat.id
    
    try:
        # Send processing message
        processing_msg = await message.reply_text("Processing your video... Please wait.")

        # Encode URL for API request
        encoded_url = quote(youtube_url)
        api_endpoint = f"{DOWNLOAD_API_URL}/download?url={encoded_url}"

        # Make API request
        response = requests.get(api_endpoint, stream=True)
        
        if response.status_code != 200:
            await processing_msg.edit_text("Failed to fetch video. Please check the URL and try again.")
            return

        # Save the video temporarily
        temp_file = "temp_video.mp4"
        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Send the video to the user
        await client.send_video(
            chat_id=chat_id,
            video=temp_file,
            caption=f"Downloaded from: {youtube_url}",
            progress=upload_progress,
            progress_args=(processing_msg,)
        )

        # Clean up
        await processing_msg.delete()
        if os.path.exists(temp_file):
            os.remove(temp_file)

    except Exception as e:
        await processing_msg.edit_text(f"An error occurred: {str(e)}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# Upload progress callback
async def upload_progress(current, total, processing_msg):
    percentage = (current / total) * 100
    await processing_msg.edit_text(f"Uploading video: {percentage:.1f}%")

# Run the bot
if __name__ == "__main__":
    app.run()
