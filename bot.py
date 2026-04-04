import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
CHANNEL = os.environ.get("CHANNEL_USERNAME", "dv_prime")
ADMIN = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))

# --- DATABASE SETUP ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["locker_database"]
users = db["users"]
config = db["config"]

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (For Render) ---
async def home(request):
    return web.Response(text="Bot is Running ✅")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", home)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- HELPER: CHECK CHANNEL JOIN ---
async def is_joined(user_id):
    try:
        member = await app.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# --- COMMAND: START ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    args = message.text.split()

    # User Registration & Referral Logic
    user_data = await users.find_one({"user_id": user_id})
    if not user_data:
        await users.insert_one({"user_id": user_id, "referrals": 0})
        # If someone joined via referral link
        if len(args) > 1 and args[1].isdigit():
            referrer = int(args[1])
            if referrer != user_id:
                await users.update_one({"user_id": referrer}, {"$inc": {"referrals": 1}})
                try:
                    await app.send_message(referrer, "🎊 किसी ने आपके लिंक से बॉट जॉइन किया!")
                except: pass

    # Get Current Referral Count
    current_data = await users.find_one({"user_id": user_id})
    count = current_data.get("referrals", 0)
    
    bot_me = await app.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={user_id}"

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL}")],
        [InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")]
    ])

    await message.reply(
        f"👋 **नमस्ते {message.from_user.first_name}!**\n\n"
        f"लिंक अनलॉक करने के लिए आपको **5 लोगों** को रिफर करना होगा।\n\n"
        f"📊 आपका स्कोर: **{count}/5**\n"
        f"🔗 आपका रिफरल लिंक:\n`{ref_link}`",
        reply_markup=btn
    )

# --- CALLBACK: CHECK STATUS ---
@app.on_callback_query(filters.regex("check"))
async def check_callback(client, callback):
    user_id = callback.from_user.id

    # 1. Check if joined channel
    if not await is_joined(user_id):
        return await callback.answer("❌ पहले चैनल जॉइन करें!", show_alert=True)

    # 2. Check referral count
    user_data = await users.find_one({"user_id": user_id})
    refs = user_data.get("referrals", 0) if user_data else 0

    if refs >= 5:
        cfg = await config.find_one({"_id": "data"})
        file_link = cfg.get("file", "Link not set yet by Admin") if cfg else "Link not set"
        await callback.message.edit_text(f"✅ **बधाई हो! मिशन पूरा हुआ।**\n\nआपकी लिंक यहाँ है:\n{file_link}")
    else:
        await callback.answer(f"⚠️ अभी सिर्फ {refs}/5 रिफरल हुए हैं। 5 पूरे करें!", show_alert=True)

# --- ADMIN: SET TARGET LINK ---
@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_file(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/set https://yourlink.com`")
    
    target = message.text.split(None, 1)[1]
    await config.update_one({"_id": "data"}, {"$set": {"file": target}}, upsert=True)
    await message.reply(f"✅ **टारगेट लिंक सेव हो गया:**\n`{target}`")

# --- MAIN RUNNER ---
async def run_everything():
    await start_web_server()
    await app.start()
    print("Bot is Fully Active with Database! ✅")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_everything())
    
