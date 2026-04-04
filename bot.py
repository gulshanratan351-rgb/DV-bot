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
config = db["config"] # यहाँ टारगेट लिंक और चैनल लिस्ट सेव होगी

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER ---
async def home(request):
    return web.Response(text="Multi-Channel Bot is Running ✅")

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

async async def is_joined(user_id):
    try:
        cfg = await config.find_one({"_id": "channels_list"})
        chans = cfg.get("list", []) if cfg else []
        
        if not chans: 
            return True 

        for ch in chans:
            try:
                # Channel ki ID ya Username nikalna
                ch_id = ch['id'] 
                
                # Agar username @ ke saath hai toh @ hatana, nahi toh direct use karna
                if isinstance(ch_id, str) and not ch_id.startswith("-100"):
                    ch_id = ch_id.replace("@", "")
                
                # Member check karna
                member = await app.get_chat_member(ch_id, user_id)
                
                # Check status
                if member.status not in ["member", "administrator", "creator"]:
                    return False
            except Exception as e:
                # Agar bot admin hai toh yahan error nahi aana chahiye
                # Agar 'User not found' aata hai toh matlab join nahi kiya
                print(f"Check failed for {ch_id}: {e}")
                return False 
        
        return True 
    except Exception as e:
        print(f"Main Error: {e}")
        return False
        
# --- COMMAND: START ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    args = message.text.split()
    
    # User Registration
    user_data = await users.find_one({"user_id": user_id})
    if not user_data:
        await users.insert_one({"user_id": user_id, "referrals": 0})
        if len(args) > 1 and args[1].isdigit():
            referrer = int(args[1])
            if referrer != user_id:
                await users.update_one({"user_id": referrer}, {"$inc": {"referrals": 1}})

    # Score & Link
    current_data = await users.find_one({"user_id": user_id})
    count = current_data.get("referrals", 0)
    bot_me = await app.get_me()
    
    # Generate Join Buttons dynamically
    channels = await get_channels()
    keyboard = []
    for index, ch in enumerate(channels, 1):
        keyboard.append([InlineKeyboardButton(f"📢 Join Channel {index}", url=f"https://t.me/{ch}")])
    
    keyboard.append([InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")])

    await message.reply(
        f"👋 **नमस्ते {message.from_user.first_name}!**\n\n"
        f"लिंक के लिए **5 रिफरल** और ऊपर दिए गए सभी चैनल जॉइन करना ज़रूरी है।\n\n"
        f"📊 आपका स्कोर: **{count}/5**\n"
        f"🔗 रिफरल लिंक: `https://t.me/{bot_me.username}?start={user_id}`",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- ADMIN COMMANDS ---

@app.on_message(filters.command("add_channel") & filters.user(ADMIN))
async def add_channel(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/add_channel channel_username` (बिना @ के)")
    
    new_ch = message.text.split(None, 1)[1].replace("@", "")
    await config.update_one({"_id": "channels_list"}, {"$addToSet": {"list": new_ch}}, upsert=True)
    await message.reply(f"✅ चैनल `@{new_ch}` लिस्ट में जोड़ दिया गया है।")

@app.on_message(filters.command("del_channel") & filters.user(ADMIN))
async def del_channel(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/del_channel channel_username`")
    
    target_ch = message.text.split(None, 1)[1].replace("@", "")
    await config.update_one({"_id": "channels_list"}, {"$pull": {"list": target_ch}})
    await message.reply(f"❌ चैनल `@{target_ch}` लिस्ट से हटा दिया गया है।")

@app.on_message(filters.command("channels") & filters.user(ADMIN))
async def list_channels(client, message):
    channels = await get_channels()
    if not channels: return await message.reply("अभी कोई चैनल सेट नहीं है।")
    msg = "**सेट किए गए चैनल्स:**\n\n" + "\n".join([f"• @{c}" for c in channels])
    await message.reply(msg)

@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_link(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/set link`")
    target = message.text.split(None, 1)[1]
    await config.update_one({"_id": "target_data"}, {"$set": {"file": target}}, upsert=True)
    await message.reply("✅ टारगेट लिंक सेट हो गया!")

# --- CHECK CALLBACK ---
@app.on_callback_query(filters.regex("check"))
async def check_callback(client, callback):
    user_id = callback.from_user.id
    if not await is_joined(user_id):
        return await callback.answer("❌ आपने सभी चैनल जॉइन नहीं किए हैं!", show_alert=True)
    
    user_data = await users.find_one({"user_id": user_id})
    if user_data and user_data.get("referrals", 0) >= 5:
        cfg = await config.find_one({"_id": "target_data"})
        link = cfg.get("file", "Link not set") if cfg else "Link not set"
        await callback.message.edit_text(f"✅ अनलॉक हो गया!\n\nलिंक: {link}")
    else:
        await callback.answer(f"⚠️ अभी रिफरल कम हैं!", show_alert=True)

# --- RUN ---
async def run_bot():
    await start_web_server()
    await app.start()
    print("Multi-Channel Admin Bot Started! ✅")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run_bot())

