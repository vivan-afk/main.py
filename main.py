
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pytube import YouTube
from pydub import AudioSegment
from youtubesearchpython import VideosSearch
import asyncio

# Telegram bot configuration (replace with your own credentials)
API_ID = "12380656"  # Telegram API ID
API_HASH = "d927c13beaaf5110f25c505b7c071273"  # Telegram API Hash
BOT_TOKEN = "8380016831:AAEYHdP6PTS0Gbd7v0I7b0fmu4OpIFZjykY"  # Telegram Bot Token


# Initialize Pyrogram client
app = Client("YouTubeMP3SearchBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Function to search YouTube and get the first video URL
def search_youtube(query):
    try:
        videos_search = VideosSearch(query, limit=1)
        results = videos_search.result()
        if results["result"]:
            video = results["result"][0]
            return video["link"], video["title"]
        return None, None
    except Exception as e:
        print(f"Search error: {e}")
        return None, None

# Function to download and convert YouTube audio to MP3
async def download_and_convert_to_mp3(url, title, message: Message):
    try:
        # Inform user that processing has started
        await message.reply_text(f"Processing: {title}")

        # Initialize YouTube object
        yt = YouTube(url)
        video_title = yt.title

        # Get the audio stream
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            await message.reply_text("No audio stream available for this video.")
            return

        # Download audio to a temporary file
        temp_file = audio_stream.download(output_path="downloads")
        base, ext = os.path.splitext(temp_file)
        mp3_file = base + ".mp3"

        # Convert to MP3 using pydub
        audio = AudioSegment.from_file(temp_file)
        audio.export(mp3_file, format="mp3")

        # Send the MP3 file to the user
        await message.reply_audio(
            audio=mp3_file,
            title=video_title,
            performer="YouTube MP3 Bot",
            duration=int(audio.duration_seconds)
        )

        # Clean up temporary files
        os.remove(temp_file)
        os.remove(mp3_file)
        await message.reply_text("MP3 sent successfully!")

    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")

# Handler for /start command
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Welcome to the YouTube MP3 Downloader Bot!\n"
        "Send me the name of a YouTube video, and I'll find it, convert it to MP3, and send it back.\n"
        "Example: Rick Astley Never Gonna Give You Up"
    )

# Handler for video name input
@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_video_name(client: Client, message: Message):
    video_name = message.text.strip()
    if not video_name:
        await message.reply_text("Please send a valid video name.")
        return

    # Search for the video
    video_url, video_title = search_youtube(video_name)
    if not video_url:
        await message.reply_text("No video found for your query. Try a different name.")
        return

    # Download and process the video
    await download_and_convert_to_mp3(video_url, video_title, message)

# Create downloads directory if it doesn't exist
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# Run the bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run()
