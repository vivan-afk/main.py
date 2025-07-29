
import os
import re
import json
import requests
import zipfile
import base64
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from typing import List, Optional, Dict, Any

# Configuration (replace with actual values)
API_ID = "12380656"  # Telegram API ID
API_HASH = "d927c13beaaf5110f25c505b7c071273"  # Telegram API Hash
BOT_TOKEN = "8380016831:AAEYHdP6PTS0Gbd7v0I7b0fmu4OpIFZjykY"  # Telegram Bot Token
MUSIC_API_URL = "https://tgmusic.fallenapi.fun"  # Music API URL
MUSIC_API_KEY = "86278b_ssueajhR0D5XCET9n3HGIr0y57w2BZeR"  # Music API Key

# Initialize Pyrogram client
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Utility Classes and Functions
class Track:
    def __init__(self, name: str, artist: str, url: str, platform: str = "spotify"):
        self.name = name
        self.artist = artist
        self.url = url
        self.platform = platform

class PlatformTracks:
    def __init__(self, results: List[Track]):
        self.results = results

class ZipResult:
    def __init__(self, zip_path: str, success_count: int, errors: List[str]):
        self.zip_path = zip_path
        self.success_count = success_count
        self.errors = errors

class ApiData:
    def __init__(self, query: str):
        self.query = query

    def is_valid(self) -> bool:
        """Check if the query is a valid Spotify URL."""
        return bool(re.match(r"https?://open\.spotify\.com/track/[\w]+", self.query))

    def get_info(self) -> Optional[PlatformTracks]:
        """Fetch track info from the API for a specific URL."""
        headers = {"Authorization": f"Bearer {MUSIC_API_KEY}"}
        try:
            response = requests.get(f"{MUSIC_API_URL}", params={"url": self.query}, headers=headers)
            response.raise_for_status()
            data = response.json()
            tracks = [Track(
                name=data.get("name", "Unknown"),
                artist=data.get("artist", "Unknown"),
                url=data.get("url", self.query),
                platform="spotify"
            )]
            return PlatformTracks(tracks)
        except requests.RequestException as e:
            print(f"Error fetching track info: {e}")
            return None

    def search(self, limit: str) -> Optional[PlatformTracks]:
        """Search for tracks using the query."""
        headers = {"Authorization": f"Bearer {MUSIC_API_KEY}"}
        try:
            response = requests.get(
                f"{MUSIC_API_URL}",
                params={"query": self.query, "limit": limit, "type": "track"},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            tracks = [
                Track(
                    name=item.get("name", "Unknown"),
                    artist=item.get("artist", "Unknown"),
                    url=item.get("url", ""),
                    platform=item.get("platform", "spotify")
                ) for item in data.get("results", [])
            ]
            return PlatformTracks(tracks)
        except requests.RequestException as e:
            print(f"Error searching tracks: {e}")
            return None

    def get_track(self) -> Optional[Track]:
        """Fetch a single track's details."""
        headers = {"Authorization": f"Bearer {MUSIC_API_KEY}"}
        try:
            response = requests.get(f"{MUSIC_API_URL}", params={"url": self.query}, headers=headers)
            response.raise_for_status()
            data = response.json()
            return Track(
                name=data.get("name", "Unknown"),
                artist=data.get("artist", "Unknown"),
                url=data.get("url", self.query),
                platform="spotify"
            )
        except requests.RequestException as e:
            print(f"Error fetching track: {e}")
            return None

def encode_url(url: str) -> str:
    """Encode a URL to base64."""
    return base64.urlsafe_b64encode(url.encode()).decode()

def decode_url(encoded: str) -> Optional[str]:
    """Decode a base64 URL."""
    try:
        return base64.urlsafe_b64decode(encoded.encode()).decode()
    except Exception as e:
        print(f"Error decoding URL: {e}")
        return None

def download_track(track: Track) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Download a track and return (audio_path, thumbnail_path, error)."""
    headers = {"Authorization": f"Bearer {MUSIC_API_KEY}"}
    try:
        response = requests.get(f"{MUSIC_API_URL}", params={"url": track.url}, headers=headers)
        response.raise_for_status()
        data = response.json()
        audio_url = data.get("audio_url")
        thumb_url = data.get("thumbnail_url")
        
        if not audio_url:
            return None, None, "No audio URL provided"
        
        # Download audio
        audio_response = requests.get(audio_url)
        audio_response.raise_for_status()
        audio_path = f"downloads/{track.name}_{track.artist}.mp3"
        os.makedirs("downloads", exist_ok=True)
        with open(audio_path, "wb") as f:
            f.write(audio_response.content)
        
        # Download thumbnail (if available)
        thumb_path = None
        if thumb_url:
            thumb_response = requests.get(thumb_url)
            thumb_response.raise_for_status()
            thumb_path = f"downloads/{track.name}_{track.artist}_thumb.jpg"
            with open(thumb_path, "wb") as f:
                f.write(thumb_response.content)
        
        return audio_path, thumb_path, None
    except requests.RequestException as e:
        return None, None, str(e)

def zip_tracks(tracks: PlatformTracks) -> ZipResult:
    """Zip multiple tracks and return the result."""
    os.makedirs("downloads", exist_ok=True)
    zip_path = "downloads/tracks.zip"
    success_count = 0
    errors = []
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for track in tracks.results:
            audio_path, _, error = download_track(track)
            if error or not audio_path or not os.path.exists(audio_path):
                errors.append(f"Failed to download {track.name} - {track.artist}: {error or 'File missing'}")
                continue
            zipf.write(audio_path, os.path.basename(audio_path))
            success_count += 1
            os.remove(audio_path)  # Clean up individual file
    
    return ZipResult(zip_path, success_count, errors)

def file_exists(path: str) -> bool:
    """Check if a file exists."""
    return os.path.exists(path)

def build_track_caption(track: Track) -> str:
    """Build caption for a track."""
    return f"🎵 {track.name} - {track.artist}"

# Telegram Handlers
@app.on_message(filters.command("song"))
async def spotify_search_song(client: Client, message: Message):
    """Handle /song command to search for and select a song."""
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    
    if not query:
        await message.reply("❗ Please provide a song name or Spotify URL.")
        return
    
    api = ApiData(query)
    keyboard = []
    
    if api.is_valid():
        tracks = api.get_info()
        if not tracks or not tracks.results:
            await message.reply("😢 Song not found.")
            return
    else:
        tracks = api.search("5")
        if not tracks or not tracks.results:
            await message.reply("😔 No results found.")
            return
    
    for track in tracks.results:
        data = f"spot_{encode_url(track.url)}_{0 if api.is_valid() else message.from_user.id}"
        keyboard.append([InlineKeyboardButton(f"{track.name} - {track.artist}", callback_data=data)])
    
    try:
        await message.reply(
            "<b>🎧 Select a song from below:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        print(f"Error sending reply: {e}")
        await message.reply("⚠️ Too many results. Please use a direct track URL or reduce playlist size.")

@app.on_callback_query(filters.regex(r"^spot_"))
async def spotify_handler_callback(client: Client, callback: CallbackQuery):
    """Handle callback queries from song selection."""
    data = callback.data
    match = re.match(r"spot_(.+)_(\d+)", data)
    if not match:
        await callback.answer("❌ Invalid selection.", show_alert=True)
        await callback.message.delete()
        return
    
    encoded_url, user_id = match.groups()
    if user_id != "0" and int(user_id) != callback.from_user.id:
        await callback.answer("🚫 This action is not meant for you.", show_alert=True)
        return
    
    await callback.answer("🔄 Processing your request...", show_alert=True)
    url = decode_url(encoded_url)
    if not url:
        await callback.message.edit("❌ Failed to decode the URL.")
        return
    
    track = ApiData(url).get_track()
    if not track:
        await callback.message.edit("❌ Could not fetch track details.")
        return
    
    msg = await callback.message.edit("⏬ Downloading the song...")
    audio_path, thumb_path, error = download_track(track)
    if error or not audio_path or not file_exists(audio_path):
        await msg.edit("⚠️ Failed to download the song.")
        return
    
    # Check if audio is a Telegram link
    telegram_match = re.match(r"https?://t\.me/([^/]+)/(\d+)", audio_path)
    if telegram_match:
        channel, msg_id = telegram_match.groups()
        try:
            telegram_msg = await client.get_messages(channel, int(msg_id))
            audio_path = await telegram_msg.download(file_name=f"downloads/{track.name}_{track.artist}.mp3")
        except Exception as e:
            await msg.edit(f"⚠️ Failed to download file: {e}")
            return
    
    if not file_exists(audio_path):
        await msg.edit("❌ Audio file missing.")
        return
    
    try:
        await msg.edit(
            build_track_caption(track),
            reply_markup=None,
            file=audio_path,
            thumb=thumb_path
        )
        print("Successfully sent track.")
    except Exception as e:
        await msg.edit(f"❌ Failed to send the track: {e}")
    finally:
        if audio_path and file_exists(audio_path):
            os.remove(audio_path)
        if thumb_path and file_exists(thumb_path):
            os.remove(thumb_path)

@app.on_message(filters.command("playlist"))
async def zip_handle(client: Client, message: Message):
    """Handle /playlist command to download multiple tracks as a ZIP."""
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    
    if not query:
        await message.reply("🎵 Please send a song name, artist, or Spotify URL.\nExample: /playlist Daft Punk Get Lucky")
        return
    
    api = ApiData(query)
    msg = await message.reply("🔍 Searching for tracks...")
    
    tracks = api.get_info() if api.is_valid() else api.search("5")
    if not tracks or not tracks.results:
        await msg.edit("⚠️ Couldn't find any tracks. Please try a different search.")
        return
    
    if tracks.results[0].platform == "youtube":
        await msg.edit("⚠️ YouTube is not supported. Please try a different search.")
        return
    
    await msg.edit(f"⏳ Found {len(tracks.results)} tracks. Preparing download...")
    
    zip_result = zip_tracks(tracks)
    if not file_exists(zip_result.zip_path):
        await msg.edit("⚠️ Download completed but zip file is missing. Please report this issue.")
        return
    
    success_msg = f"✅ Success! Downloaded {zip_result.success_count}/{len(tracks.results)} tracks.\n📦 Zip file ready:"
    if zip_result.errors:
        success_msg += f"\n\n⚠️ {len(zip_result.errors)} tracks failed to download."
    
    try:
        await msg.edit(
            success_msg,
            file=zip_result.zip_path,
            caption=f"🎵 {zip_result.success_count} tracks"
        )
    except Exception as e:
        await msg.edit(f"❌ Failed to send zip file: {e}")
    finally:
        if file_exists(zip_result.zip_path):
            os.remove(zip_result.zip_path)

# Run the bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run()
