from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import os, asyncio
from aiohttp import web

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
CHANNEL = os.environ.get("CHANNEL_USERNAME", "")
ADMIN = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))

# --- DB ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["locker"]
users = db["users"]
config = db["config"]

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER ---
async def home(request):
    return web.Response(text="Bot is Running ✅")

async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get("/", home)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- CHECK JOIN ---
async def is_joined(user_id):
    if not CHANNEL:
        return True
    try:
        member = await app.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Join Check Error: {e}")
        return False

# --- START ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    try:
        # Step 1: Immediate Reply
        await message.reply("⚡ बॉट एक्टिव है, डेटा चेक किया जा रहा है...")
        
        user_id = message.from_user.id
        args = message.text.split()

        # Step 2: Database Update
        await users.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {"referrals": 0}},
            upsert=True
        )

        # Step 3: Referral Logic
        if len(args) > 1:
            referrer = args[1]
            if referrer.isdigit() and int(referrer) != user_id:
                await users.update_one(
                    {"user_id": int(referrer)},
                    {"$inc": {"referrals": 1}}
                )

        # Step 4: Buttons
        bot_user = await app.get_me()
        link = f"https://t.me/{bot_user.username}?start={user_id}"

        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL}")],
            [InlineKeyboardButton("🔁 Check / Unlock", callback_data="check")]
        ])

        await message.reply(
            f"🔒 **लिंक अनलॉक करने के लिए 5 लोगों को इनवाइट करें।**\n\n"
            f"🔗 आपका इनवाइट लिंक:\n`{link}`",
            reply_markup=btn
        )
    except Exception as e:
        await message.reply(f"❌ एरर आया: {e}")

# --- CHECK CALLBACK ---
@app.on_callback_query(filters.regex("check"))
async def check(client, callback):
    try:
        user_id = callback.from_user.id

        if not await is_joined(user_id):
            await callback.answer("❌ पहले चैनल जॉइन करें!", show_alert=True)
            return

        data = await users.find_one({"user_id": user_id})
        refs = data.get("referrals", 0) if data else 0

        if refs >= 5:
            cfg = await config.find_one({"_id": "data"})
            file_link = cfg.get("file", "No link set") if cfg else "No link set"
            await callback.message.reply(f"✅ मिशन पूरा! आपकी लिंक यहाँ है:\n{file_link}")
        else:
            await callback.answer(f"⚠️ अभी सिर्फ {refs} रिफरल हुए हैं। 5 पूरे करें!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ एरर: {e}", show_alert=True)

# --- ADMIN ---
@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_file(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/set https://link.com`")
    link = message.text.split(None, 1)[1]
    await config.update_one({"_id": "data"}, {"$set": {"file": link}}, upsert=True)
    await message.reply("✅ टारगेट लिंक सेट हो गया!")

# --- RUN ---
async def main():
    async with app:
        await start_web_server()
        print("Bot is Alive...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
    
