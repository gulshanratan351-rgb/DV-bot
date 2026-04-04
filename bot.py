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
ADMIN = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 8080))

# --- DATABASE ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["multi_channel_db"]
users = db["users"]
config = db["config"]

app = Client("dv_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (For Render) ---
async def home(request):
    return web.Response(text="Bot is Alive ✅")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", home)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

# --- HELPER: JOIN CHECK ---
async def is_joined(user_id):
    cfg = await config.find_one({"_id": "channels_list"})
    channels = cfg.get("list", []) if cfg else []
    
    for ch in channels:
        try:
            # ID को स्ट्रिंग से नंबर में बदलना सबसे ज़रूरी है
            c_id = int(str(ch['id']).strip())
            member = await app.get_chat_member(c_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"Join Check Error: {e}")
            # अगर बॉट एडमिन नहीं है, तो भी हम यहाँ False भेजेंगे ताकि यूजर को पता चले
            return False
    return True

# --- COMMAND: START ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    text = message.text.split()

    # User Setup
    user_data = await users.find_one({"user_id": user_id})
    if not user_data:
        await users.insert_one({"user_id": user_id, "referrals": 0})
        if len(text) > 1 and text[1].isdigit():
            ref_id = int(text[1])
            if ref_id != user_id:
                await users.update_one({"user_id": ref_id}, {"$inc": {"referrals": 1}})
                try: await client.send_message(ref_id, "🎊 किसी ने आपके लिंक से जॉइन किया!")
                except: pass

    # Get Data for Buttons
    u_data = await users.find_one({"user_id": user_id})
    count = u_data.get("referrals", 0) if u_data else 0
    cfg = await config.find_one({"_id": "channels_list"})
    channels = cfg.get("list", []) if cfg else []
    
    keyboard = []
    for i, ch in enumerate(channels, 1):
        keyboard.append([InlineKeyboardButton(f"📢 Join Channel {i}", url=ch['link'])])
    
    keyboard.append([InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")])
    
    bot_username = (await client.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    await message.reply(
        f"👋 **नमस्ते {message.from_user.first_name}!**\n\n"
        f"लिंक के लिए 5 रिफरल और चैनल जॉइन करना ज़रूरी है।\n\n"
        f"📊 आपका स्कोर: **{count}/5**\n"
        f"🔗 लिंक: `{ref_link}`",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- ADMIN COMMANDS ---

@app.on_message(filters.command("clear_all") & filters.user(ADMIN))
async def clear_all(client, message):
    await config.delete_one({"_id": "channels_list"})
    await message.reply("🧹 साफ़ कर दिया गया!")

@app.on_message(filters.command("add_channel") & filters.user(ADMIN))
async def add_channel(client, message):
    args = message.text.split()
    if len(args) < 3:
        return await message.reply("लिखें: `/add_channel ID LINK`")
    
    await config.update_one(
        {"_id": "channels_list"}, 
        {"$addToSet": {"list": {"id": args[1], "link": args[2]}}}, 
        upsert=True
    )
    await message.reply("✅ चैनल जुड़ गया!")

@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_link(client, message):
    args = message.text.split(None, 1)
    if len(args) < 2: return await message.reply("लिखें: `/set LINK`")
    await config.update_one({"_id": "target"}, {"$set": {"link": args[1]}}, upsert=True)
    await message.reply("✅ मूवी लिंक सेट!")

# --- CALLBACK ---
@app.on_callback_query(filters.regex("check"))
async def check(client, callback):
    if not await is_joined(callback.from_user.id):
        return await callback.answer("❌ पहले सभी चैनल जॉइन करें!", show_alert=True)
    
    u = await users.find_one({"user_id": callback.from_user.id})
    if u and u.get("referrals", 0) >= 5:
        target = await config.find_one({"_id": "target"})
        link = target.get("link", "Set link first") if target else "Set link first"
        await callback.message.edit_text(f"✅ मिशन पूरा! लिंक: {link}")
    else:
        await callback.answer(f"⚠️ अभी 5 रिफरल पूरे नहीं हुए!", show_alert=True)

# --- START ---
async def main():
    await start_web_server()
    await app.start()
    print("DV BOT IS ONLINE ✅")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
