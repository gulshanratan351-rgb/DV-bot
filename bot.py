from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os, threading
from aiohttp import web

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
CHANNEL = os.environ.get("CHANNEL_USERNAME")
ADMIN = int(os.environ.get("ADMIN_ID"))

# --- DB ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["locker"]
users = db["users"]
config = db["config"]

# --- BOT ---
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- CHECK JOIN ---
async def is_joined(user_id):
    try:
        member = await app.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# --- START ---
@app.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    args = message.text.split()

    await users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {"referrals": 0}},
        upsert=True
    )

    if len(args) > 1:
        referrer = int(args[1])
        if referrer != user_id:
            await users.update_one(
                {"user_id": referrer},
                {"$inc": {"referrals": 1}}
            )

    link = f"https://t.me/{(await app.get_me()).username}?start={user_id}"

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL}")],
        [InlineKeyboardButton("🔁 Check", callback_data="check")]
    ])

    await message.reply(
        f"🔒 Share this link with 5 users:\n\n{link}",
        reply_markup=btn
    )

# --- CHECK ---
@app.on_callback_query(filters.regex("check"))
async def check(client, callback):
    user_id = callback.from_user.id

    if not await is_joined(user_id):
        await callback.answer("पहले channel join करो!", show_alert=True)
        return

    data = await users.find_one({"user_id": user_id})
    refs = data.get("referrals", 0)

    cfg = await config.find_one({"_id": "data"})
    file_link = cfg.get("file", "No file set")

    if refs >= 5:
        await callback.message.reply(f"✅ Unlock:\n{file_link}")
    else:
        await callback.answer(f"{5-refs} referrals बाकी", show_alert=True)

# ================= ADMIN ================= #

@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_file(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /set link")

    await config.update_one(
        {"_id": "data"},
        {"$set": {"file": message.command[1]}},
        upsert=True
    )

    await message.reply("✅ File set")

@app.on_message(filters.command("users") & filters.user(ADMIN))
async def users_count(client, message):
    count = await users.count_documents({})
    await message.reply(f"👥 Users: {count}")

# ================= WEB SERVER ================= #

async def home(request):
    return web.Response(text="Bot is Running ✅")

def run_web():
    app_web = web.Application()
    app_web.router.add_get("/", home)
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app_web, host="0.0.0.0", port=port)

# --- RUN BOTH ---
threading.Thread(target=run_web).start()
app.run()
