from pyrogram import Client, filters
from youtubesearchpython.__future__ import VideosSearch
import asyncio

# Telegram bot configuration
app = Client(
    "YouTubeSearchBot",
    api_id="12380656",  # Replace with your Telegram API ID
    api_hash="d927c13beaaf5110f25c505b7c071273",  # Replace with your Telegram API Hash
    bot_token="8380016831:AAEYHdP6PTS0Gbd7v0I7b0fmu4OpIFZjykY"  # Replace with your Bot Token from BotFather
)

# Message handler for text messages (song names)
@app.on_message(filters.text)
async def search_videos(client, message):
    try:
        song_name = message.text
        await message.reply_text(f"Searching for videos related to: {song_name}...")

        # Perform YouTube search
        videosSearch = VideosSearch(song_name, limit=2)
        videosResult = await videosSearch.next()

        # Process and format results
        if videosResult["result"]:
            response = "Here are the top results:\n\n"
            for video in videosResult["result"]:
                title = video["title"]
                link = video["link"]
                channel = video["channel"]["name"]
                duration = video["duration"]
                response += f"**{title}**\nChannel: {channel}\nDuration: {duration}\nLink: {link}\n\n"
            await message.reply_text(response)
        else:
            await message.reply_text("No videos found for your search.")
    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")

# Run the bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run()
