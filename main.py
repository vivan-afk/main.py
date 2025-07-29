import asyncio
import logging
import requests
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import urlparse, parse_qs
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = "12380656"
API_HASH = "d927c13beaaf5110f25c505b7c071273"
BOT_TOKEN = "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU"
API_BASE_URL = "https://tgmusic.fallenapi.fun"  # Base URL
API_KEY = "739c4b_uADhloSh7dPJYQzawlxDUZ-l4zVqvY4b"

# Initialize the bot
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Helper function to check if user is admin
async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR)
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

# Helper function to extract Spotify track ID from URL
def extract_spotify_id(url: str) -> str:
    try:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        if 'track' in path_parts:
            return path_parts[-1].split('?')[0]
        return ""
    except Exception as e:
        logger.error(f"Error extracting Spotify ID: {e}")
        return ""

# Helper function to fetch track metadata
async def get_track_metadata(track_id: str) -> dict:
    try:
        # Replace with actual endpoint, e.g., f"{API_BASE_URL}/track/{track_id}"
        url = f"{API_BASE_URL}/track/{track_id}"  # Update this URL based on API docs
        headers = {
            "X-API-Key": API_KEY.strip(),  # Strip whitespace from API key
            # Alternative headers if needed (uncomment and adjust based on API docs)
            # "Authorization": f"Bearer {API_KEY}",
            # "api-key": API_KEY
        }
        logger.info(f"Sending request to {url} with headers: {headers}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raises an HTTPError for bad status codes
        if not response.content:
            logger.error("Empty response from track metadata API")
            return {"error": "Empty response from API"}
        try:
            data = response.json()
            logger.info(f"Received response: {data}")
            if "error" in data and data["error"] == "Missing API Key":
                logger.error("API returned 'Missing API Key' error")
                return {"error": "Invalid or missing API key"}
            return data
        except ValueError as e:
            logger.error(f"Invalid JSON response: {response.text}")
            return {"error": f"Invalid JSON response: {str(e)}"}
    except HTTPError as e:
        logger.error(f"HTTP error fetching track metadata: {e}, Response: {response.text}")
        return {"error": f"HTTP error: {str(e)}, Response: {response.text}"}
    except (ConnectionError, Timeout) as e:
        logger.error(f"Network error fetching track metadata: {e}")
        return {"error": f"Network error: {str(e)}"}
    except RequestException as e:
        logger.error(f"Error fetching track metadata: {e}")
        return {"error": str(e)}

# Helper function to fetch lyrics
async def get_lyrics(track_id: str) -> dict:
    try:
        # Replace with actual endpoint, e.g., f"{API_BASE_URL}/lyrics/{track_id}"
        url = f"{API_BASE_URL}/lyrics/{track_id}"  # Update this URL based on API docs
        headers = {
            "X-API-Key": API_KEY.strip(),
            # Alternative headers if needed
            # "Authorization": f"Bearer {API_KEY}",
            # "api-key": API_KEY
        }
        logger.info(f"Sending request to {url} with headers: {headers}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        if not response.content:
            logger.error("Empty response from lyrics API")
            return {"error": "Empty response from API"}
        try:
            data = response.json()
            logger.info(f"Received response: {data}")
            if "error" in data and data["error"] == "Missing API Key":
                logger.error("API returned 'Missing API Key' error")
                return {"error": "Invalid or missing API key"}
            return data
        except ValueError as e:
            logger.error(f"Invalid JSON response: {response.text}")
            return {"error": f"Invalid JSON response: {str(e)}"}
    except HTTPError as e:
        logger.error(f"HTTP error fetching lyrics: {e}, Response: {response.text}")
        return {"error": f"HTTP error: {str(e)}, Response: {response.text}"}
    except (ConnectionError, Timeout) as e:
        logger.error(f"Network error fetching lyrics: {e}")
        return {"error": f"Network error: {str(e)}"}
    except RequestException as e:
        logger.error(f"Error fetching lyrics: {e}")
        return {"error": str(e)}

# Helper function to search tracks
async def search_tracks(query: str, limit: int = 5) -> dict:
    try:
        # Replace with actual endpoint, e.g., f"{API_BASE_URL}/search?query={query}&limit={limit}"
        url = f"{API_BASE_URL}/search?query={query}&limit={limit}"  # Update this URL based on API docs
        headers = {
            "X-API-Key": API_KEY.strip(),
            # Alternative headers if needed
            # "Authorization": f"Bearer {API_KEY}",
            # "api-key": API_KEY
        }
        logger.info(f"Sending request to {url} with headers: {headers}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        if not response.content:
            logger.error("Empty response from search tracks API")
            return {"error": "Empty response from API"}
        try:
            data = response.json()
            logger.info(f"Received response: {data}")
            if "error" in data and data["error"] == "Missing API Key":
                logger.error("API returned 'Missing API Key' error")
                return {"error": "Invalid or missing API key"}
            return data
        except ValueError as e:
            logger.error(f"Invalid JSON response: {response.text}")
            return {"error": f"Invalid JSON response: {str(e)}"}
    except HTTPError as e:
        logger.error(f"HTTP error searching tracks: {e}, Response: {response.text}")
        return {"error": f"HTTP error: {str(e)}, Response: {response.text}"}
    except (ConnectionError, Timeout) as e:
        logger.error(f"Network error searching tracks: {e}")
        return {"error": f"Network error: {str(e)}"}
    except RequestException as e:
        logger.error(f"Error searching tracks: {e}")
        return {"error": str(e)}

# Command handler for /start
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    response = (
        "🎵 Welcome to the Spotify Music Downloader Bot! 🎵\n\n"
        "Send a Spotify track URL or type a song name to get metadata and download options.\n"
        "Available commands:\n"
        "/id - Get chat/user ID\n"
        "/ban - Ban a user (admin only)\n"
        "/unban - Unban a user (admin only)"
    )
    await message.reply_text(response, parse_mode=enums.ParseMode.MARKDOWN)

# Command handler for /id
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    try:
        chat_id = message.chat.id
        response = f"**Chat ID**: `{chat_id}`\n"

        if message.reply_to_message:
            user = message.reply_to_message.from_user
            response += f"**User ID**: `{user.id}`\n"
            response += f"**Username**: @{user.username if user.username else 'None'}\n"
            response += f"**First Name**: {user.first_name}\n"
            if user.last_name:
                response += f"**Last Name**: {user.last_name}\n"
            response += f"**Is Bot**: {'Yes' if user.is_bot else 'No'}\n"
        
        elif len(message.command) > 1:
            username = message.command[1].lstrip('@')
            try:
                user = await client.get_users(username)
                response += f"**User ID**: `{user.id}`\n"
                response += f"**Username**: @{user.username if user.username else 'None'}\n"
                response += f"**First Name**: {user.first_name}\n"
                if user.last_name:
                    response += f"**Last Name**: {user.last_name}\n"
                response += f"**Is Bot**: {'Yes' if user.is_bot else 'No'}\n"
            except Exception as e:
                response += f"Error: Could not find user @{username}"
        
        await message.reply_text(response, parse_mode=enums.ParseMode.MARKDOWN)
    
    except Exception as e:
        logger.error(f"Error in id_command: {e}")
        await message.reply_text("An error occurred while processing the command.")

# Command handler for /ban
@app.on_message(filters.command("ban") & filters.group)
async def ban_command(client: Client, message: Message):
    try:
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("You must be an admin to use this command.")
            return

        if message.reply_to_message:
            user = message.reply_to_message.from_user
            if user:
                if await is_admin(client, message.chat.id, user.id):
                    await message.reply_text("Cannot ban an admin!")
                    return
                
                reason = " ".join(message.command[1:]) if len(message.command) > 1 else "No reason provided"
                await client.ban_chat_member(message.chat.id, user.id)
                response = f"**Banned User**: @{user.username if user.username else user.first_name}\n"
                response += f"**User ID**: `{user.id}`\n"
                response += f"**Reason**: {reason}"
                await message.reply_text(response, parse_mode=enums.ParseMode.MARKDOWN)
            else:
                await message.reply_text("Could not identify the user to ban.")
        
        elif len(message.command) > 1:
            username = message.command[1].lstrip('@')
            try:
                user = await client.get_users(username)
                if await is_admin(client, message.chat.id, user.id):
                    await message.reply_text("Cannot ban an admin!")
                    return
                
                reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
                await client.ban_chat_member(message.chat.id, user.id)
                response = f"**Banned User**: @{user.username if user.username else user.first_name}\n"
                response += f"**User ID**: `{user.id}`\n"
                response += f"**Reason**: {reason}"
                await message.reply_text(response, parse_mode=enums.ParseMode.MARKDOWN)
            except Exception as e:
                await message.reply_text(f"Error: Could not find user @{username}")
        
        else:
            await message.reply_text("Please reply to a message or provide a username to ban.")
    
    except Exception as e:
        logger.error(f"Error in ban_command: {e}")
        await message.reply_text("An error occurred while processing the ban command.")

# Command handler for /unban
@app.on_message(filters.command("unban") & filters.group)
async def unban_command(client: Client, message: Message):
    try:
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("You must be an admin to use this command.")
            return

        if len(message.command) > 1:
            username = message.command[1].lstrip('@')
            try:
                user = await client.get_users(username)
                await client.unban_chat_member(message.chat.id, user.id)
                response = f"**Unbanned User**: @{user.username if user.username else user.first_name}\n"
                response += f"**User ID**: `{user.id}`"
                await message.reply_text(response, parse_mode=enums.ParseMode.MARKDOWN)
            except Exception as e:
                await message.reply_text(f"Error: Could not find user @{username}")
        else:
            await message.reply_text("Please provide a username to unban.")
    
    except Exception as e:
        logger.error(f"Error in unban_command: {e}")
        await message.reply_text("An error occurred while processing the unban command.")

# Handler for Spotify URLs
@app.on_message(filters.regex(r"https://open\.spotify\.com/track/[\w\d]+"))
async def spotify_url_handler(client: Client, message: Message):
    try:
        spotify_url = message.text
        track_id = extract_spotify_id(spotify_url)
        
        if not track_id:
            await message.reply_text("Invalid Spotify URL. Please provide a valid track URL.")
            return

        # Fetch track metadata
        metadata = await get_track_metadata(track_id)
        if "error" in metadata:
            await message.reply_text(f"Error fetching metadata: {metadata['error']}")
            return

        # Fetch lyrics
        lyrics_data = await get_lyrics(track_id)
        lyrics = lyrics_data.get("results", "Lyrics not available")

        # Format response
        duration = metadata.get('duration', 0)
        minutes = duration // 60
        seconds = duration % 60
        response = (
            f"🎵 **Track Info** 🎵\n\n"
            f"**Name**: {metadata.get('name', 'Unknown')}\n"
            f"**Artist**: {', '.join(metadata.get('artists', ['Unknown']))}\n"
            f"**Album**: {metadata.get('album', 'Unknown')}\n"
            f"**Year**: {metadata.get('year', 'Unknown')}\n"
            f"**Duration**: {minutes}:{seconds:02d}\n"
            f"\n**Lyrics Preview**:\n{lyrics[:200] + '...' if len(lyrics) > 200 else lyrics}\n"
        )

        # Create inline buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Download", url=metadata.get('cdnurl', '')),
                InlineKeyboardButton("Full Lyrics", callback_data=f"lyrics_{track_id}")
            ]
        ])

        await message.reply_text(
            response,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error processing Spotify URL: {e}")
        await message.reply_text("An error occurred while processing the Spotify URL.")

# Handler for text queries (song names)
@app.on_message(filters.text & ~filters.command(["start", "id", "ban", "unban"]) & ~filters.regex(r"https://open\.spotify\.com/track/[\w\d]+"))
async def song_query_handler(client: Client, message: Message):
    try:
        query = message.text.strip()
        if not query:
            await message.reply_text("Please provide a song name to search.")
            return

        # Search for tracks
        search_results = await search_tracks(query)
        if "error" in search_results:
            await message.reply_text(f"Error searching for tracks: {search_results['error']}")
            return

        # Get the first result
        results = search_results.get("results", [])
        if not results:
            await message.reply_text(f"No tracks found for '{query}'.")
            return

        # Use the first track for metadata and lyrics
        track = results[0]
        track_id = track.get('id')
        if not track_id:
            await message.reply_text("No valid track ID found in search results.")
            return

        # Fetch detailed metadata
        metadata = await get_track_metadata(track_id)
        if "error" in metadata:
            await message.reply_text(f"Error fetching metadata: {metadata['error']}")
            return

        # Fetch lyrics
        lyrics_data = await get_lyrics(track_id)
        lyrics = lyrics_data.get("results", "Lyrics not available")

        # Format response
        duration = metadata.get('duration', track.get('duration', 0))
        minutes = duration // 60
        seconds = duration % 60
        response = (
            f"🎵 **Track Info** 🎵\n\n"
            f"**Name**: {metadata.get('name', track.get('name', 'Unknown'))}\n"
            f"**Artist**: {', '.join(metadata.get('artists', [track.get('artist', 'Unknown')]))}\n"
            f"**Album**: {metadata.get('album', track.get('album', 'Unknown'))}\n"
            f"**Year**: {metadata.get('year', track.get('year', 'Unknown'))}\n"
            f"**Duration**: {minutes}:{seconds:02d}\n"
            f"\n**Lyrics Preview**:\n{lyrics[:200] + '...' if len(lyrics) > 200 else lyrics}\n"
        )

        # Create inline buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Download", url=metadata.get('cdnurl', '')),
                InlineKeyboardButton("Full Lyrics", callback_data=f"lyrics_{track_id}")
            ]
        ])

        await message.reply_text(
            response,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error processing song query: {e}")
        await message.reply_text("An error occurred while processing the song query.")

# Callback handler for inline buttons
@app.on_callback_query(filters.regex(r"lyrics_.*"))
async def lyrics_callback(client: Client, callback_query):
    try:
        track_id = callback_query.data.split("_")[1]
        lyrics_data = await get_lyrics(track_id)
        lyrics = lyrics_data.get("results", "Lyrics not available")
        
        await callback_query.message.reply_text(
            f"🎵 **Full Lyrics** 🎵\n\n{lyrics}",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in lyrics callback: {e}")
        await callback_query.message.reply_text("An error occurred while fetching lyrics.")
        await callback_query.answer()

# Start the bot
if __name__ == "__main__":
    logger.info("Starting the bot...")
    app.run()
