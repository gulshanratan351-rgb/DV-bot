import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_async_engine import AsyncIOMotorClient
from aiohttp import web

# --- Configurations ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_URI", "")
CHANNELS = [int(x) for x in os.environ.get("CHANNELS", "").split(",") if x]
TARGET_LINK = os.environ.get("TARGET_LINK", "")
PORT = int(os.environ.get("PORT", 8080))

# Database Setup
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.bot_database
users_col = db.users

bot = Client("ForceShareBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Web Server for Render ---
async def handle(request):
    return web.Response(text="Bot is Alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- Bot Logic ---
async def is_subscribed(user_id):
    if not CHANNELS: return True
    for chat_id in CHANNELS:
        try:
            await bot.get_chat_member(chat_id, user_id)
        except Exception:
            return False
    return True

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    command_args = message.text.split()
    referrer_id = command_args[1] if len(command_args) > 1 else None

    if not await is_subscribed(user_id):
        buttons = []
        for i, channel in enumerate(CHANNELS, 1):
            buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=f"https://t.me/example{i}")])
        return await message.reply(
            "❌ **Access Denied!**\n\nलिंक अनलॉक करने के लिए सभी चैनल्स जॉइन करें।",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    user_data = await users_col.find_one({"user_id": user_id})
    if not user_data:
        await users_col.insert_one({"user_id": user_id, "ref_count": 0})
        if referrer_id and int(referrer_id) != user_id:
            await users_col.update_one({"user_id": int(referrer_id)}, {"$inc": {"ref_count": 1}})
            try:
                await bot.send_message(int(referrer_id), "🎉 किसी ने आपके लिंक से जॉइन किया!")
            except: pass

    user_data = await users_col.find_one({"user_id": user_id})
    count = user_data.get("ref_count", 0)

    if count >= 5:
        await message.reply(f"✅ **अनलॉक हो गया!**\n\nलिंक: {TARGET_LINK}", disable_web_page_preview=True)
    else:
        bot_username = (await bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        await message.reply(
            f"🔗 **लिंक लॉक है!**\n\nइसे अनलॉक करने के लिए 5 लोगों को शेयर करें।\n\n📊 आपका स्कोर: **{count}/5**\n📌 आपका लिंक: `{ref_link}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 शेयर करें", url=f"https://t.me/share/url?url={ref_link}")]])
        )

# --- Main Logic ---
async def main():
    async with bot:
        await start_web_server()
        print("Bot and Web Server started!")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
    
