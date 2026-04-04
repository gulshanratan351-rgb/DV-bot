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

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (For Render) ---
async def home(request):
    return web.Response(text="Bot is Alive ✅")

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
    try:
        await message.reply(
            f"नमस्ते {message.from_user.first_name}!\n\n"
            "आखिरकार! बॉट काम कर रहा है। 🚀"
        )
    except Exception as e:
        print(f"Reply Error: {e}")

# --- RUN EVERYTHING ---
if __name__ == "__main__":
    # वेब सर्वर को बैकग्राउंड में चलाने के लिए
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    
    print("Bot is starting via app.run()...")
    app.run()
    
