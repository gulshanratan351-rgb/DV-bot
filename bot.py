import os
import base64
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# ENV VARIABLES
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_DB = os.environ.get("MONGO_DB")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
CHANNEL = os.environ.get("CHANNEL")  # @channelusername

# DATABASE
mongo = MongoClient(MONGO_DB)
db = mongo["file_store_bot"]
files = db["files"]
settings = db["settings"]

# BOT
app = Client("file_store_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# AUTO DELETE TIME
def get_time():
    data = settings.find_one({"_id": "time"})
    return data["time"] if data else 300  # default 5 min

# CHECK FORCE SUB
async def is_joined(client, user_id):
    try:
        member = await client.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# START COMMAND
@app.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id

    # FORCE SUB CHECK
    if not await is_joined(client, user_id):
        btn = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL.replace('@','')}")],
                [InlineKeyboardButton("✅ Check Again", callback_data="checksub")]
            ]
        )
        return await message.reply("🚫 पहले channel join करो!", reply_markup=btn)

    # FILE ACCESS
    if len(message.command) > 1:
        try:
            file_id = base64.urlsafe_b64decode(message.command[1].encode()).decode()
            msg = await message.reply_document(file_id)

            # AUTO DELETE
            time = get_time()
            await asyncio.sleep(time)
            await msg.delete()
            await message.delete()

        except:
            await message.reply("❌ File not found or expired")
    else:
        await message.reply("👋 Send me any file and get a shareable link")

# CHECK BUTTON
@app.on_callback_query(filters.regex("checksub"))
async def check_sub(client, callback_query):
    user_id = callback_query.from_user.id

    if await is_joined(client, user_id):
        await callback_query.message.delete()
        await callback_query.message.reply("✅ Access Granted! अब /start दबाओ")
    else:
        await callback_query.answer("❌ अभी join नहीं किया", show_alert=True)

# HELP COMMAND
@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    await message.reply("""
📌 Commands:
/start - Start bot
/help - Help menu
/settime 60 - Auto delete time (admin)
/batch - Batch upload start (admin)
/stop - Stop batch (admin)

📂 Send any file to store and get link
""")

# SET AUTO DELETE TIME
@app.on_message(filters.command("settime") & filters.user(ADMIN_ID))
async def set_time(client, message):
    try:
        t = int(message.command[1])
        settings.update_one({"_id": "time"}, {"$set": {"time": t}}, upsert=True)
        await message.reply(f"✅ Auto delete time set to {t} seconds")
    except:
        await message.reply("❌ Use like: /settime 60")

# SAVE FILE
@app.on_message(filters.document | filters.video | filters.audio)
async def save_file(client, message):
    file_id = message.document.file_id if message.document else \
              message.video.file_id if message.video else \
              message.audio.file_id

    files.insert_one({"file_id": file_id})

    encoded = base64.urlsafe_b64encode(file_id.encode()).decode()
    bot_username = (await client.get_me()).username
    link = f"https://t.me/{bot_username}?start={encoded}"

    await message.reply(f"✅ File Saved!\n🔗 Link:\n{link}")

# BATCH MODE
batch_mode = {}

@app.on_message(filters.command("batch") & filters.user(ADMIN_ID))
async def batch(client, message):
    batch_mode[message.from_user.id] = True
    await message.reply("📂 Send multiple files now")

@app.on_message(filters.document & filters.user(ADMIN_ID))
async def batch_save(client, message):
    if batch_mode.get(message.from_user.id):
        file_id = message.document.file_id
        files.insert_one({"file_id": file_id})
        await message.reply("✅ Added to batch")

@app.on_message(filters.command("stop") & filters.user(ADMIN_ID))
async def stop_batch(client, message):
    batch_mode[message.from_user.id] = False
    await message.reply("🛑 Batch stopped")

# RUN
app.run()
