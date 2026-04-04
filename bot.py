import os
import asyncio
import logging
import sys
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
from datetime import datetime

# ==========================================
# 1. LOGGING & DEBUGGING (गलती पकड़ने के लिए)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot_log.txt"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. CONFIGURATION (Environment Variables)
# ==========================================
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6158373752"))
PORT = int(os.environ.get("PORT", 8080))

# ==========================================
# 3. DATABASE INITIALIZATION
# ==========================================
try:
    mongo_client = AsyncIOMotorClient(MONGO_URL)
    db = mongo_client["DV_MOVIE_PRO_DB"]
    users_db = db["all_users"]
    config_db = db["bot_config"]
    logger.info("Successfully connected to MongoDB! ✅")
except Exception as e:
    logger.error(f"MongoDB Connection Failed: {e}")
    sys.exit(1)

# ==========================================
# 4. BOT CLIENT
# ==========================================
app = Client(
    "dv_pro_max_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=None
)

# ==========================================
# 5. WEB SERVER (For Render 24/7)
# ==========================================
async def handle_web(request):
    return web.Response(text="Bot is running stable 100% ✅")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_web)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

# ==========================================
# 6. ADVANCE HELPERS (Join Check & Data)
# ==========================================
async def check_user_joined(user_id):
    """सबसे एडवांस जॉइन चेक - जो कभी फेल नहीं होगा"""
    config = await config_db.find_one({"_id": "settings"})
    channels = config.get("channels", []) if config else []
    
    if not channels:
        return True

    for ch in channels:
        try:
            # Username/ID को क्लीन करना
            raw_id = str(ch['id']).strip().replace("@", "")
            # अगर -100 है तो Integer, नहीं तो String
            final_id = int(raw_id) if raw_id.startswith("-") or raw_id.isdigit() else raw_id
            
            member = await app.get_chat_member(final_id, user_id)
            if member.status in ["kicked", "left"]:
                return False
        except errors.UserNotParticipant:
            return False
        except Exception as e:
            logger.warning(f"Error checking {ch['id']}: {e}")
            return False
    return True

# ==========================================
# 7. MAIN HANDLERS (Commands)
# ==========================================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    # Registration & Referral Logic
    user = await users_db.find_one({"user_id": user_id})
    if not user:
        await users_db.insert_one({"user_id": user_id, "referrals": 0, "date": datetime.now()})
        # Check for referral link
        if len(message.command) > 1 and message.command[1].isdigit():
            ref_id = int(message.command[1])
            if ref_id != user_id:
                await users_db.update_one({"user_id": ref_id}, {"$inc": {"referrals": 1}})
                try:
                    await client.send_message(ref_id, "🎊 **बधाई हो! एक नया मेंबर आपके लिंक से जुड़ा है।**")
                except: pass

    # Get Data
    user_data = await users_db.find_one({"user_id": user_id})
    refs = user_data.get("referrals", 0)
    config = await config_db.find_one({"_id": "settings"})
    channels = config.get("channels", []) if config else []
    
    # Keyboard Setup
    buttons = []
    for i, ch in enumerate(channels, 1):
        buttons.append([InlineKeyboardButton(f"📢 Join Channel {i}", url=ch['link'])])
    
    buttons.append([InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="verify_join")])
    
    bot_info = await client.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

    text = (
        f"👋 **नमस्ते {name}!**\n\n"
        f"मूवी लिंक अनलॉक करने के लिए आपको **5 रिफरल** और हमारे सभी चैनल जॉइन करने होंगे।\n\n"
        f"📊 **आपका स्कोर:** `{refs}/5` रिफरल्स\n"
        f"🔗 **आपका रिफरल लिंक:**\n`{ref_link}`"
    )
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ==========================================
# 8. ADMIN TOOLS (Add, Clear, Set)
# ==========================================

@app.on_message(filters.command("add_channel") & filters.user(ADMIN_ID))
async def admin_add_channel(client, message):
    if len(message.command) < 3:
        return await message.reply("❌ **Format:** `/add_channel username_ya_id link`")
    
    ch_id = message.command[1].strip().replace("@", "")
    ch_link = message.command[2].strip()
    
    await config_db.update_one(
        {"_id": "settings"},
        {"$addToSet": {"channels": {"id": ch_id, "link": ch_link}}},
        upsert=True
    )
    await message.reply(f"✅ **सफलतापूर्वक जुड़ गया!**\nTarget: `{ch_id}`")

@app.on_message(filters.command("clear_all") & filters.user(ADMIN_ID))
async def admin_clear(client, message):
    await config_db.update_one({"_id": "settings"}, {"$set": {"channels": []}})
    await message.reply("🧹 **चैनल लिस्ट साफ़ कर दी गई!**")

@app.on_message(filters.command("set") & filters.user(ADMIN_ID))
async def admin_set_movie(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Format:** `/set https://movierg.com`")
    
    movie_link = message.text.split(None, 1)[1]
    await config_db.update_one({"_id": "settings"}, {"$set": {"movie_link": movie_link}}, upsert=True)
    await message.reply("✅ **मूवी लिंक सेट हो गया!**")

# ==========================================
# 9. CALLBACKS (Button Verification)
# ==========================================

@app.on_callback_query(filters.regex("verify_join"))
async def verification_callback(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not await check_user_joined(user_id):
        return await callback.answer("❌ आपने अभी तक सभी चैनल जॉइन नहीं किए हैं!", show_alert=True)
    
    user_data = await users_db.find_one({"user_id": user_id})
    score = user_data.get("referrals", 0)
    
    if score >= 5:
        config = await config_db.find_one({"_id": "settings"})
        link = config.get("movie_link", "Link not set yet")
        await callback.message.edit_text(
            f"✅ **मिशन पूरा!**\n\nआपकी मूवी यहाँ है:\n{link}",
            disable_web_page_preview=True
        )
    else:
        await callback.answer(f"⚠️ अभी {score}/5 रिफरल हुए हैं। थोड़ा और शेयर करें!", show_alert=True)

# ==========================================
# 10. SYSTEM START
# ==========================================

async def main():
    logger.info("Starting Web Server...")
    await start_web_server()
    logger.info("Starting Bot Client...")
    await app.start()
    logger.info("DV MOVIE ULTRA PRO MAX IS READY ✅")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot Stopped!")
        
