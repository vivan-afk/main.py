import asyncio
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message
import os

# configuration
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
            response = await client.get(
                API_URL,
                headers=headers,
                params={"query": song_name}
            )
            response.raise_for_status()
            # Check if response is valid audio content
            content_type = response.headers.get("content-type", "")
            if "audio/mpeg" not in content_type:
                print(f"Invalid content type received: {content_type}")
                return None
            output_file = f"downloads/{song_name}.mp3"
            os.makedirs("downloads", exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(response.content)
            # Verify file is not empty
            if os.path.getsize(output_file) == 0:
                print("Downloaded file is empty")
                os.remove(output_file)
                return None
            return output_file
    except Exception as e:
        print(f"Error downloading song: {e}")
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
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {str(e)}")

print("Bot is running...")
app.run()
