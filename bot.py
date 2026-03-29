import os
import asyncio
import logging
import random
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG (Render Environment Variables) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_DB", "") # Aapke Render variable ke hisab se
ADMIN = int(os.environ.get("ADMIN_ID", "0"))
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "0"))

# --- INITIALIZE ---
bot = Client("FileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["FileStoreDB"]
fsub_col = db["fsub_settings"]

# --- FLASK FOR RENDER (Keep Alive) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Online and Healthy!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# --- HELPER FUNCTIONS ---
async def is_subscribed(client, message):
    config = await fsub_col.find_one({"id": "config"})
    if not config: return True
    try:
        await client.get_chat_member(config["channel_id"], message.from_user.id)
        return True
    except UserNotParticipant: return False
    except: return True

# --- ADMIN COMMANDS ---
@bot.on_message(filters.command("set_fsub") & filters.user(ADMIN))
async def set_fsub(client, message):
    try:
        args = message.text.split()
        if len(args) < 3:
            return await message.reply_text("❌ **Format:** `/set_fsub -100xxx ChannelUsername`")
        
        ch_id = int(args[1])
        ch_user = args[2].replace("@", "")
        await fsub_col.update_one({"id": "config"}, {"$set": {"channel_id": ch_id, "username": ch_user}}, upsert=True)
        await message.reply_text(f"✅ **Force Subscribe Updated!**\n🆔 `{ch_id}`\n👤 @{ch_user}")
    except Exception as e: await message.reply_text(f"❌ Error: {e}")

# --- FILE STORE LOGIC ---
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio) & filters.user(ADMIN))
async def store_file(client, message):
    msg = await message.forward(DB_CHANNEL)
    link = f"https://t.me/{(await client.get_me()).username}?start=file_{msg.id}"
    await message.reply_text(f"✅ **File Stored!**\n\nLink: `{link}`")

# --- START HANDLER ---
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # Force Subscribe Check
    if not await is_subscribed(client, message):
        config = await fsub_col.find_one({"id": "config"})
        btn = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{config['username']}")],
               [InlineKeyboardButton("✅ Check Again", url=f"https://t.me/{(await client.get_me()).username}?start={message.command[1] if len(message.command) > 1 else ''}")]]
        return await message.reply_text("🚫 **Pehle channel join karo!**", reply_markup=InlineKeyboardMarkup(btn))

    # File Delivery
    if len(message.command) > 1 and message.command[1].startswith("file_"):
        try:
            f_id = int(message.command[1].split("_")[1])
            sent_msg = await client.copy_message(message.chat.id, DB_CHANNEL, f_id)
            
            # Auto-Delete Logic
            del_msg = await message.reply_text("⚠️ Ye file **60 seconds** mein delete ho jayegi!")
            await asyncio.sleep(60)
            await sent_msg.delete()
            await del_msg.edit("🗑️ **File auto-delete ho gayi hai.**")
        except: await message.reply_text("❌ File nahi mili.")
    else:
        await message.reply_text(f"👋 Hello {message.from_user.mention}!\n\nMain ek File Store bot hoon. File link par click karein.")

# --- RUN BOT ---
async def main():
    # Flask ko alag thread mein chalayein
    Thread(target=run_flask).start()
    
    await bot.start()
    logger.info("🚀 Bot is Live on Render!")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
    
