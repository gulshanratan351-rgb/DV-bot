import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("MONGO_URI")
ADMIN = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID")) # Force Subscribe ke liye
DB_CHANNEL = int(os.getenv("DB_CHANNEL")) # Jahan files save hongi

bot = Client("FileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db_client = AsyncIOMotorClient(DB_URL)
db = db_client["FileStoreDB"]["files"]

# --- FORCE SUBSCRIBE CHECK ---
async def is_subscribed(client, message):
    try:
        await client.get_chat_member(CHANNEL_ID, message.from_user.id)
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True

# --- FILE STORAGE LOGIC ---
@bot.on_message(filters.private & (filters.document | filters.video | filters.photo))
async def store_file(client, message):
    if message.from_user.id != ADMIN:
        return
    
    # File ko database channel mein forward karna
    log_msg = await message.forward(DB_CHANNEL)
    file_id = log_msg.id
    
    # Link generate karna
    share_link = f"https://t.me/{(await client.get_me()).username}?start=file_{file_id}"
    await message.reply_text(f"✅ **File Stored!**\n\nLink: `{share_link}`")

# --- START & AUTO-DELETE LOGIC ---
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # 1. Force Subscribe Check
    if not await is_subscribed(client, message):
        invite_link = (await client.get_chat(CHANNEL_ID)).invite_link
        btn = [[InlineKeyboardButton("Join Channel", url=invite_link)]]
        return await message.reply_text("❌ Pehle channel join karein tabhi file milegi!", reply_markup=InlineKeyboardMarkup(btn))

    # 2. File Delivery
    if len(message.command) > 1 and message.command[1].startswith("file_"):
        file_id = int(message.command[1].split("_")[1])
        
        try:
            sent_msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=DB_CHANNEL,
                message_id=file_id
            )
            
            # --- AUTO DELETE FEATURE (60 Seconds) ---
            await message.reply_text("⚠️ Ye file **60 seconds** mein delete ho jayegi. Jaldi save kar lo!")
            await asyncio.sleep(60)
            await sent_msg.delete()
            await message.reply_text("🗑️ File auto-delete ho gayi hai.")
            
        except Exception as e:
            await message.reply_text("❌ File nahi mili ya delete ho gayi hai.")
    else:
        await message.reply_text("👋 Welcome! Main files store kar sakta hoon.")

print("Bot Started...")
bot.run()
