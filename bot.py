import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# --- CONFIG (Using .get() to avoid KeyError) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL") or os.environ.get("MONGO_URI", "")
CHANNEL = os.environ.get("CHANNEL_USERNAME", "")
ADMIN = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))

# --- DATABASE SETUP ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["locker_database"]
users = db["users"]
config = db["config"]

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER FOR RENDER ---
async def home(request):
    return web.Response(text="Bot is Running ✅")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", home)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- HELPER: CHECK JOIN ---
async def is_joined(user_id):
    if not CHANNEL:
        return True
    try:
        member = await app.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Join Check Error: {e}")
        return False

# --- COMMAND: START ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    try:
        user_id = message.from_user.id
        args = message.text.split()

        # Step 1: Database Registration
        user_data = await users.find_one({"user_id": user_id})
        if not user_data:
            await users.insert_one({"user_id": user_id, "referrals": 0})
            # Referral logic
            if len(args) > 1 and args[1].isdigit():
                referrer = int(args[1])
                if referrer != user_id:
                    await users.update_one({"user_id": referrer}, {"$inc": {"referrals": 1}})
                    try:
                        await app.send_message(referrer, "🎊 किसी ने आपके लिंक से बॉट जॉइन किया है!")
                    except: pass

        # Step 2: UI Logic
        bot_me = await app.get_me()
        link = f"https://t.me/{bot_me.username}?start={user_id}"
        
        # Get current referral count
        current_data = await users.find_one({"user_id": user_id})
        count = current_data.get("referrals", 0)

        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL}")],
            [InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")]
        ])

        await message.reply(
            f"👋 **नमस्ते {message.from_user.first_name}!**\n\n"
            f"लिंक अनलॉक करने के लिए आपको **5 लोगों** को रिफर करना होगा।\n\n"
            f"📊 आपका स्कोर: **{count}/5**\n"
            f"🔗 आपका लिंक: `{link}`",
            reply_markup=btn
        )
    except Exception as e:
        print(f"Start Error: {e}")

# --- CALLBACK: CHECK STATUS ---
@app.on_callback_query(filters.regex("check"))
async def check_callback(client, callback):
    try:
        user_id = callback.from_user.id

        if not await is_joined(user_id):
            return await callback.answer("❌ पहले चैनल जॉइन करें!", show_alert=True)

        user_data = await users.find_one({"user_id": user_id})
        refs = user_data.get("referrals", 0) if user_data else 0

        if refs >= 5:
            cfg = await config.find_one({"_id": "data"})
            file_link = cfg.get("file", "No link set yet") if cfg else "No link set"
            await callback.message.edit_text(f"✅ **मिशन पूरा! आपकी लिंक यहाँ है:**\n\n{file_link}")
        else:
            await callback.answer(f"⚠️ अभी सिर्फ {refs}/5 रिफरल हुए हैं। 5 पूरे करें!", show_alert=True)
    except Exception as e:
        await callback.answer(f"Error: {e}", show_alert=True)

# --- ADMIN: SET LINK ---
@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_file(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/set https://yourlink.com`")
    
    target = message.text.split(None, 1)[1]
    await config.update_one({"_id": "data"}, {"$set": {"file": target}}, upsert=True)
    await message.reply(f"✅ **टारगेट लिंक सेव हो गया:**\n`{target}`")

# --- MAIN RUNNER ---
async def main():
    async with app:
        await start_web_server()
        print("Bot is Alive and Web Server Started... ✅")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
    
