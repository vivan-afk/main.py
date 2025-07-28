import logging
import os
import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from urllib.parse import quote
import tempfile
from bs4 import BeautifulSoup

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU")
MUSIC_API_KEY = os.getenv("MUSIC_API_KEY", "86278b_ssueajhR0D5XCET9n3HGIr0y57w2BZeR")
MUSIC_API_URL = "https://tgmusic.fallenapi.fun"

# Headers for music API requests
HEADERS = {
    "Authorization": f"Bearer {MUSIC_API_KEY}",
    "User-Agent": "TelegramMusicBot/1.0"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm a music bot. Use /search <song name> to find and download a song as MP3!\n"
        "For example: /search Shape of You\n"
        "Use /help for more info."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the /help command is issued."""
    await update.message.reply_text(
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/search <song name> - Search and download a song as MP3\n"
        "Note: Songs are downloaded from tgmusic.fallenapi.fun and sent as MP3 files."
    )

def search_song(query: str) -> dict:
    """Search for a song using the music API and parse HTML response."""
    try:
        # Encode the query and construct the search URL
        
        url = f"{MUSIC_API_URL}"
        logger.info(f"Searching API with URL: {url}")
        
        # Make the API request
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        # Log response details for debugging
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response content: {response.text[:500]}")  # Log first 500 chars
        
        # Parse HTML response
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Assume song data is in a div with class 'song' (adjust based on actual HTML)
        song_elements = soup.find_all("div", class_="song")
        if not song_elements:
            logger.warning("No song elements found in HTML")
            return None
        
        # Extract details from the first song
        song = song_elements[0]
        title = song.find("h3").text.strip() if song.find("h3") else "Unknown Title"
        download_url = song.find("a", href=True)["href"] if song.find("a", href=True) else None
        
        if not download_url:
            logger.warning("No download URL found in song element")
            return None
        
        # Return song data as a dictionary
        return {"title": title, "download_url": download_url}
    except requests.RequestException as e:
        logger.error(f"Error searching song: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing HTML: {e}")
        return None

def download_song(download_url: str) -> str:
    """Download the song and return the path to the temporary file."""
    try:
        response = requests.get(download_url, headers=HEADERS, stream=True, timeout=10)
        response.raise_for_status()
        
        # Create a temporary file to store the MP3
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        temp_file.close()
        return temp_file.name
    except requests.RequestException as e:
        logger.error(f"Error downloading song: {e}")
        return None

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /search command to find and send a song."""
    if not context.args:
        await update.message.reply_text("Please provide a song name. Usage: /search <song name>")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"Searching for '{query}'...")

    # Search for the song
    song_data = search_song(query)
    if not song_data:
        await update.message.reply_text("Sorry, no results found or an error occurred.")
        return

    # Extract song details
    title = song_data.get("title", "Unknown Title")
    download_url = song_data.get("download_url")
    if not download_url:
        await update.message.reply_text("No download URL found for this song.")
        return

    # Download the song
    file_path = download_song(download_url)
    if not file_path:
        await update.message.reply_text("Failed to download the song.")
        return

    # Send the MP3 file
    try:
        with open(file_path, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=title,
                filename=f"{title}.mp3"
            )
        await update.message.reply_text(f"Sent: {title}")
    except Exception as e:
        logger.error(f"Error sending audio: {e}")
        await update.message.reply_text("Failed to send the audio file.")
    finally:
        # Clean up the temporary file
        try:
            if file_path:
                os.unlink(file_path)
        except OSError as e:
            logger.error(f"Error deleting temporary file: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
