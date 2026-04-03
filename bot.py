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

# --- DB ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["locker"]
users = db["users"]

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
        f"🔒 Share this link with 5 friends:\n\n{link}\n\n📌 Join channel first!",
        reply_markup=btn
    )

# --- CHECK BUTTON ---
@app.on_callback_query(filters.regex("check"))
async def check(client, callback):
    user_id = callback.from_user.id

    # FORCE JOIN CHECK
    if not await is_joined(user_id):
        await callback.answer("पहले channel join करो!", show_alert=True)
        return

    data = await users.find_one({"user_id": user_id})
    refs = data.get("referrals", 0)

    if refs >= 5:
        await callback.message.reply(
            "✅ Unlock Success!\n\nHere is your file:\nhttps://example.com/file"
        )
    else:
        await callback.answer(f"❌ {5-refs} referrals बाकी हैं", show_alert=True)

app.run()
