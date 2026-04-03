import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL_USERNAME", "dv_prime") # अपना चैनल यूजरनेम यहाँ डालें
PORT = int(os.environ.get("PORT", 8080))

app = Client("simple_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (Render को चालू रखने के लिए) ---
async def home(request):
    return web.Response(text="Bot is Running ✅")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", home)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # जैसे ही कोई /start भेजेगा, उसे यह मैसेज मिलेगा
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL}")],
        [InlineKeyboardButton("✅ चेक करें", callback_data="check")]
    ])
    
    await message.reply(
        f"नमस्ते {message.from_user.first_name}!\n\nआगे बढ़ने के लिए हमारे चैनल को जॉइन करें।",
        reply_markup=btn
    )

# --- CHECK BUTTON LOGIC ---
@app.on_callback_query(filters.regex("check"))
async def check_callback(client, callback):
    user_id = callback.from_user.id
    try:
        # चेक कर रहा है कि यूजर चैनल में है या नहीं
        member = await app.get_chat_member(CHANNEL, user_id)
        if member.status in ["member", "administrator", "creator"]:
            await callback.message.edit_text("✅ शुक्रिया जॉइन करने के लिए! ये रहा आपका लिंक: https://google.com")
        else:
            await callback.answer("❌ आपने अभी तक जॉइन नहीं किया है!", show_alert=True)
    except Exception as e:
        await callback.answer("⚠️ एरर: बॉट को चैनल में Admin बनाएँ!", show_alert=True)

# --- RUN BOT ---
async def main():
    async with app:
        await start_web_server()
        print("Bot Started! ✅")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
    
