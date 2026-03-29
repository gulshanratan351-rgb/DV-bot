import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIG (Apni Details Daalo) ---
API_ID = int(os.getenv("API_ID", "12345")) # my.telegram.org se lo
API_HASH = os.getenv("API_HASH", "abcdef...") 
BOT_TOKEN = os.getenv("BOT_TOKEN", "7890:ABC...")
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://...")
ADMIN = int(os.getenv("ADMIN_ID", "12345678")) # Teri Telegram ID
DB_CHANNEL = int(os.getenv("DB_CHANNEL", "-100...")) # Jahan files save hongi

bot = Client("FileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["FileStoreDB"]
fsub_col = db["fsub_settings"]

# --- FORCE SUBSCRIBE CHECK LOGIC ---
async def is_subscribed(client, message):
    config = await fsub_col.find_one({"id": "config"})
    if not config:
        return True # Agar koi channel set nahi hai toh allow karo
    
    try:
        await client.get_chat_member(config["channel_id"], message.from_user.id)
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True

# --- ADMIN COMMANDS (FSUB SET KARNE KE LIYE) ---
@bot.on_message(filters.command("set_fsub") & filters.user(ADMIN))
async def set_fsub(client, message):
    try:
        args = message.text.split()
        if len(args) < 3:
            return await message.reply_text("❌ **Format:** `/set_fsub -100123456 ID_USER_NAME`")
        
        ch_id = int(args[1])
        ch_user = args[2].replace("@", "")
        
        await fsub_col.update_one(
            {"id": "config"}, 
            {"$set": {"channel_id": ch_id, "username": ch_user}}, 
            upsert=True
        )
        await message.reply_text(f"✅ **Force Subscribe Updated!**\n🆔 ID: `{ch_id}`\n👤 User: @{ch_user}")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# --- FILE STORE LOGIC (Sirf Admin ke liye) ---
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio) & filters.user(ADMIN))
async def store_file(client, message):
    msg = await message.forward(DB_CHANNEL)
    file_link = f"https://t.me/{(await client.get_me()).username}?start=file_{msg.id}"
    await message.reply_text(f"✅ **File Stored!**\n\nLink: `{file_link}`")

# --- START HANDLER (With Auto-Delete) ---
@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # 1. Force Subscribe Check
    subscribed = await is_subscribed(client, message)
    if not subscribed:
        config = await fsub_col.find_one({"id": "config"})
        btn = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{config['username']}")] ,
               [InlineKeyboardButton("✅ Check Again", url=f"https://t.me/{(await client.get_me()).username}?start={message.command[1] if len(message.command) > 1 else ''}")]]
        return await message.reply_text("🚫 **Pehle channel join karo!**\n\nBhai, niche diye gaye channel ko join karne ke baad hi links milenge.", reply_markup=InlineKeyboardMarkup(btn))

    # 2. File Delivery
    if len(message.command) > 1 and message.command[1].startswith("file_"):
        try:
            file_id = int(message.command[1].split("_")[1])
            sent_msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=DB_CHANNEL,
                message_id=file_id
            )
            
            # --- AUTO DELETE LOGIC ---
            del_msg = await message.reply_text("⚠️ Ye file **60 seconds** mein delete ho jayegi. Jaldi save kar lo!")
            await asyncio.sleep(60)
            await sent_msg.delete()
            await del_msg.edit("🗑️ **File auto-delete ho gayi hai.**")
            
        except Exception:
            await message.reply_text("❌ File nahi mili ya database se delete ho gayi hai.")
    else:
        await message.reply_text(f"👋 Hello {message.from_user.mention}!\n\nMain ek File Store bot hoon. Link par click karke apni file le lo.")

print("Bot is running...")
bot.run()
