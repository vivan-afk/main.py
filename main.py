from pyrogram import Client, filters, enums
from pyrogram.types import Message
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = "12380656"  # Replace with your API ID
API_HASH = "d927c13beaaf5110f25c505b7c071273"  # Replace with your API Hash
BOT_TOKEN = "8380016831:AAFpRCUXqKE1EMXtETW03ec6NmUHm4xAgBU"  # Replace with your Bot Token

# Initialize the bot
app = Client("id_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Command handler for /id
@app.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    try:
        chat_id = message.chat.id
        response = f"**Chat ID**: `{chat_id}`\n"

        # Check if the command is a reply to another message
        if message.reply_to_message:
            user = message.reply_to_message.from_user
            response += f"**User ID**: `{user.id}`\n"
            response += f"**Username**: @{user.username if user.username else 'None'}\n"
            response += f"**First Name**: {user.first_name}\n"
            if user.last_name:
                response += f"**Last Name**: {user.last_name}\n"
            response += f"**Is Bot**: {'Yes' if user.is_bot else 'No'}\n"
        
        # Check if there's a mention in the command (e.g., /id @username)
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

# Start the bot
if __name__ == "__main__":
    logger.info("Starting the bot...")
    app.run()
