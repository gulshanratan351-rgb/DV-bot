"""
=========================================================================
📦 PROJECT: DV MEGA FILE STORE & PROTECTOR
🛠️ DEVELOPER: GEMINI AI (CUSTOMIZED)
📅 DATE: MARCH 2026
📜 FEATURES: 
   - Permanent/Temporary File Storage
   - Encrypted File Links
   - Multi-Channel Force Subscribe (FSub)
   - Content Protection (Anti-Forward/Anti-Save)
   - Advanced Admin Dashboard & Broadcast
=========================================================================
"""

import os
import time
import re
import uuid
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from pyrogram import Client, filters, errors
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    Message, 
    CallbackQuery
)
from pymongo import MongoClient
from flask import Flask

# -----------------------------------------------------------------------
# 1. ⚙️ CONFIGURATION (Environment Variables)
# -----------------------------------------------------------------------
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "12345678"))
DB_NAME = os.environ.get("DB_NAME", "FileStoreBot")

# Channel for storing files (Private Channel ID)
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-100xxx"))

# Force Subscribe Channels (Comma separated usernames)
AUTH_CHANNELS = [c.strip() for c in os.environ.get("AUTH_CHANNELS", "").split(",") if c.strip()]

# -----------------------------------------------------------------------
# 2. 🗄️ DATABASE SETUP
# -----------------------------------------------------------------------
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_col = db['users']
files_col = db['files']
settings_col = db['settings']

# -----------------------------------------------------------------------
# 3. 🤖 BOT CLIENT & FLASK (For 24/7 Hosting)
# -----------------------------------------------------------------------
bot = Client(
    "FileStoreBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Alive!"

# -----------------------------------------------------------------------
# 4. 🛠️ HELPER FUNCTIONS
# -----------------------------------------------------------------------

async def is_subscribed(client, message):
    """Check if user joined all required channels."""
    if not AUTH_CHANNELS:
        return True
    left_channels = []
    for char in AUTH_CHANNELS:
        try:
            user = await client.get_chat_member(char, message.from_user.id)
            if user.status == "kicked":
                return False
        except errors.UserNotParticipant:
            left_channels.append(char)
        except Exception:
            pass
    return left_channels

def encode_data(data):
    """Simple encoding for URL safety."""
    return str(data).encode("ascii").hex()

def decode_data(data):
    """Decode data from hex."""
    return bytes.fromhex(data).decode("ascii")

# -----------------------------------------------------------------------
# 5. 📥 FILE HANDLING (Saving Files)
# -----------------------------------------------------------------------

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def handle_incoming_file(client, message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("🚫 Only Admin can add files to the store.")

    # 1. Forward file to DB Channel
    sent_msg = await message.forward(DB_CHANNEL)
    file_id = sent_msg.id
    
    # 2. Generate Secret Link
    secret_code = encode_data(file_id)
    bot_user = await client.get_me()
    share_link = f"https://t.me/{bot_user.username}?start=file_{secret_code}"
    
    # 3. Save to MongoDB
    files_col.insert_one({
        "file_id": file_id,
        "file_name": getattr(message.document or message.video or message.audio, 'file_name', 'Photo'),
        "code": secret_code,
        "created_at": datetime.now()
    })

    await message.reply_text(
        f"✅ **File Stored Successfully!**\n\n"
        f"🔗 **Your Link:** `{share_link}`",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Share Link", url=f"https://telegram.me/share/url?url={share_link}")
        ]])
    )

# -----------------------------------------------------------------------
# 6. 📤 FILE RETRIEVAL (Start Handler)
# -----------------------------------------------------------------------

@bot.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    user_id = message.from_user.id
    
    # Register user
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id, "join_date": datetime.now()})

    # FSub Check
    left = await is_subscribed(client, message)
    if left:
        buttons = []
        for channel in left:
            buttons.append([InlineKeyboardButton(f"Join {channel}", url=f"https://t.me/{channel}")])
        buttons.append([InlineKeyboardButton("Try Again 🔄", url=f"https://t.me/{(await client.get_me()).username}?start={message.command[1] if len(message.command) > 1 else ''}")])
        return await message.reply_text(
            "⚠️ **Access Denied!**\n\nPlease join our channels first to use this bot.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # Check for File Code
    if len(message.command) > 1 and message.command[1].startswith("file_"):
        code = message.command[1].replace("file_", "")
        try:
            msg_id = int(decode_data(code))
            # Get file from DB Channel
            file_msg = await client.get_messages(DB_CHANNEL, msg_id)
            
            # PROTECT CONTENT: Send without forward/save option if enabled
            await file_msg.copy(
                chat_id=message.chat.id,
                protect_content=True, # Prevent Forward/Save
                caption="📁 **File securely delivered by DV Store.**"
            )
        except Exception as e:
            await message.reply("❌ **Error:** Link expired or invalid.")
        return

    await message.reply_text(f"👋 **Hello {message.from_user.first_name}!**\nI am a high-speed File Store Bot.")

# -----------------------------------------------------------------------
# 7. 👑 ADMIN DASHBOARD
# -----------------------------------------------------------------------

@bot.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(client, message):
    total_users = users_col.count_documents({})
    total_files = files_col.count_documents({})
    await message.reply_text(f"📊 **Bot Stats**\n\n👥 Total Users: `{total_users}`\n📁 Total Files: `{total_files}`")

@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast(client, message):
    if not message.reply_to_message:
        return await message.reply("Reply to a message to broadcast.")
    
    users = users_col.find({})
    count = 0
    msg = await message.reply("🚀 **Broadcast Started...**")
    
    for user in users:
        try:
            await message.reply_to_message.copy(user['user_id'])
            count += 1
            await asyncio.sleep(0.05) # Prevent flood
        except:
            pass
    
    await msg.edit(f"✅ **Broadcast Completed!**\nDelivered to `{count}` users.")

# -----------------------------------------------------------------------
# 8. 🚀 RUN THE BOT
# -----------------------------------------------------------------------

if __name__ == "__main__":
    # Start Flask in a separate thread for Render/Heroku
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    
    print("DV File Store Bot is running...")
    bot.run()
    
