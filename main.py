
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

# Helper function to check if user is admin
async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR)
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

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

# Command handler for /ban
@app.on_message(filters.command("ban") & filters.group)
async def ban_command(client: Client, message: Message):
    try:
        # Check if the user is an admin
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("You must be an admin to use this command.")
            return

        # Check if it's a reply to a message
        if message.reply_to_message:
            user = message.reply_to_message.from_user
            if user:
                # Prevent banning admins
                if await is_admin(client, message.chat.id, user.id):
                    await message.reply_text("Cannot ban an admin!")
                    return
                
                # Get ban reason if provided
                reason = " ".join(message.command[1:]) if len(message.command) > 1 else "No reason provided"
                
                # Ban the user
                await client.ban_chat_member(message.chat.id, user.id)
                response = f"**Banned User**: @{user.username if user.username else user.first_name}\n"
                response += f"**User ID**: `{user.id}`\n"
                response += f"**Reason**: {reason}"
                await message.reply_text(response, parse_mode=enums.ParseMode.MARKDOWN)
            else:
                await message.reply_text("Could not identify the user to ban.")
        
        # Check if username is provided
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
        # Check if the user is an admin
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("You must be an admin to use this command.")
            return

        # Check if username is provided
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

# Start the bot
if __name__ == "__main__":
    logger.info("Starting the bot...")
    app.run()
