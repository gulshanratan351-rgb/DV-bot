from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os

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

    # REF SYSTEM
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
        [InlineKeyboardButton("🔁 Check Status", callback_data="check")]
    ])

    await message.reply(
        f"🔒 Share this link with 5 friends:\n\n{link}",
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
        await callback.answer(f"{5-refs} referrals बाकी हैं", show_alert=True)

# ================= ADMIN PANEL ================= #

# SET FILE
@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_file(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /set https://link")

    link = message.command[1]

    await config.update_one(
        {"_id": "data"},
        {"$set": {"file": link}},
        upsert=True
    )

    await message.reply("✅ File/Link set successfully")

# USER COUNT
@app.on_message(filters.command("users") & filters.user(ADMIN))
async def user_count(client, message):
    count = await users.count_documents({})
    await message.reply(f"👥 Total Users: {count}")

# BROADCAST
@app.on_message(filters.command("broadcast") & filters.user(ADMIN))
async def broadcast(client, message):
    if not message.reply_to_message:
        return await message.reply("Reply to a message")

    msg = message.reply_to_message
    all_users = users.find()

    sent = 0
    async for user in all_users:
        try:
            await msg.copy(user["user_id"])
            sent += 1
        except:
            pass

    await message.reply(f"✅ Sent to {sent} users")

# ADMIN PANEL VIEW
@app.on_message(filters.command("admin") & filters.user(ADMIN))
async def admin_panel(client, message):
    await message.reply(
        "🔧 Admin Panel\n\n"
        "/set link\n"
        "/users\n"
        "/broadcast (reply)"
    )

# --- RUN ---
app.run()
