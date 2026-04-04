import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# --- CONFIG (Render के Variables यहाँ से लोड होंगे) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
ADMIN = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))

# --- DATABASE SETUP ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["multi_channel_db"]
users = db["users"]
config = db["config"]

app = Client("dv_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (Render को जगाए रखने के लिए) ---
async def home(request):
    return web.Response(text="Bot is Active and Multi-Channel Ready ✅")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", home)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- HELPERS ---
async def get_channels():
    cfg = await config.find_one({"_id": "channels_list"})
    return cfg.get("list", []) if cfg else []

async def is_joined(user_id):
    channels = await get_channels()
    for ch in channels:
        try:
            # ID से मेंबरशिप चेक करना (प्राइवेट चैनल के लिए बेस्ट)
            member = await app.get_chat_member(int(ch['id']), user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"Check Error for {ch['id']}: {e}")
            return False
    return True

# --- COMMAND: START ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    args = message.text.split()
    
    # User Registration & Referral Logic
    user_data = await users.find_one({"user_id": user_id})
    if not user_data:
        await users.insert_one({"user_id": user_id, "referrals": 0})
        if len(args) > 1 and args[1].isdigit():
            referrer = int(args[1])
            if referrer != user_id:
                await users.update_one({"user_id": referrer}, {"$inc": {"referrals": 1}})
                try: await client.send_message(referrer, "🎊 किसी ने आपके लिंक से जॉइन किया!")
                except: pass

    current_data = await users.find_one({"user_id": user_id})
    count = current_data.get("referrals", 0)
    bot_me = await app.get_me()
    
    channels = await get_channels()
    keyboard = []
    # डायनामिक बटन बनाना (असली लिंक के साथ)
    for index, ch in enumerate(channels, 1):
        keyboard.append([InlineKeyboardButton(f"📢 Join Channel {index}", url=ch['link'])])
    
    keyboard.append([InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")])

    ref_link = f"https://t.me/{bot_me.username}?start={user_id}"
    
    await message.reply(
        f"👋 **नमस्ते {message.from_user.first_name}!**\n\n"
        f"मूवी लिंक अनलॉक करने के लिए **5 रिफरल** और सभी चैनल जॉइन करना ज़रूरी है।\n\n"
        f"📊 आपका स्कोर: **{count}/5**\n"
        f"🔗 आपका रिफरल लिंक:\n`{ref_link}`",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- ADMIN COMMANDS ---

@app.on_message(filters.command("clear_all") & filters.user(ADMIN))
async def clear_all(client, message):
    await config.delete_one({"_id": "channels_list"})
    await message.reply("🧹 **डेटाबेस साफ़!** अब नए सिरे से /add_channel इस्तेमाल करें।")

@app.on_message(filters.command("add_channel") & filters.user(ADMIN))
async def add_channel(client, message):
    args = message.text.split()
    if len(args) < 3:
        return await message.reply("❌ **गलत तरीका!**\n\nऐसे लिखें: `/add_channel -100123456789 https://t.me/+joinlink` \n\n(ID और Link के बीच में स्पेस दें)")
    
    ch_id = args[1]
    ch_link = args[2]
    
    await config.update_one(
        {"_id": "channels_list"}, 
        {"$addToSet": {"list": {"id": ch_id, "link": ch_link}}}, 
        upsert=True
    )
    await message.reply(f"✅ **चैनल जुड़ गया!**\nID: `{ch_id}`\nLink: {ch_link}")

@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_link(client, message):
    args = message.text.split(None, 1)
    if len(args) < 2: return await message.reply("लिखें: `/set https://movierg.com`")
    target = args[1]
    await config.update_one({"_id": "target_data"}, {"$set": {"file": target}}, upsert=True)
    await message.reply("✅ **टारगेट मूवी लिंक सेट हो गया!**")

@app.on_message(filters.command("channels") & filters.user(ADMIN))
async def list_channels(client, message):
    channels = await get_channels()
    if not channels: return await message.reply("कोई चैनल सेट नहीं है।")
    msg = "**सेट किए गए चैनल्स की ID:**\n\n" + "\n".join([f"• `{c['id']}`" for c in channels])
    await message.reply(msg)

# --- CHECK CALLBACK ---
@app.on_callback_query(filters.regex("check"))
async def check_callback(client, callback):
    user_id = callback.from_user.id
    if not await is_joined(user_id):
        return await callback.answer("❌ आपने अभी सभी चैनल जॉइन नहीं किए हैं!", show_alert=True)
    
    user_data = await users.find_one({"user_id": user_id})
    refs = user_data.get("referrals", 0) if user_data else 0
    
    if refs >= 5:
        cfg = await config.find_one({"_id": "target_data"})
        link = cfg.get("file", "Link not set") if cfg else "Link not set"
        await callback.message.edit_text(f"✅ **बधाई हो! लिंक अनलॉक हो गया:**\n\n{link}")
    else:
        await callback.answer(f"⚠️ अभी सिर्फ {refs}/5 रिफरल हुए हैं। 5 पूरे करें!", show_alert=True)

# --- RUN BOT ---
async def start_bot():
    await start_web_server()
    await app.start()
    print("DV Movie Bot is Online! 🚀")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
    
