import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

# --- BOT CLIENT ---
app = Client("my_simple_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER ---
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
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url="https://t.me/dv_prime")],
        [InlineKeyboardButton("🛠 Support", url="https://t.me/your_username")]
    ])
    
    try:
        await message.reply(
            f"स्वागत है {message.from_user.first_name}!\n\n"
            "मैं आपका ऑटो-रिप्लाई बॉट हूँ। अभी मैं पूरी तरह चालू हूँ! 🚀\n\n"
            "नीचे दिए गए बटनों का उपयोग करें:",
            reply_markup=buttons
        )
    except Exception as e:
        print(f"Error occurred: {e}")

# --- MAIN RUNNER ---
async def main():
    # 'async with app' का इस्तेमाल सुरक्षित है
    async with app:
        await start_web_server()
        print("Bot is Alive and Ready! ✅")
        await asyncio.Future()

if __name__ == "__main__":
    # सीधा run करना सबसे बेहतर तरीका है
    asyncio.run(main())
    
