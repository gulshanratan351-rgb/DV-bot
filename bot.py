import os, asyncio, logging
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
ADMIN = int(os.environ.get("ADMIN_ID", "6158373752"))
PORT = int(os.environ.get("PORT", 8080))

app = Client("dv_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["DV_PRO_DATABASE"]
users = db["users"]
config = db["config"]

# --- ⭐ WEB SERVER (ISKI WAJAH SE ERROR AA RAHA THA) ---
async def start_web():
    server = web.Application()
    server.router.add_get("/", lambda r: web.Response(text="Bot is Alive ✅"))
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web Server started on port {PORT}")

# --- JOIN CHECK ---
async def is_joined(user_id):
    try:
        cfg = await config.find_one({"_id": "channels_list"})
        chans = cfg.get("list", []) if cfg else []
        if not chans: return True
        for ch in chans:
            raw_id = str(ch['id']).strip().replace("@", "")
            target = int(raw_id) if raw_id.startswith("-") or raw_id.isdigit() else raw_id
            member = await app.get_chat_member(target, user_id)
            if member.status in ["kicked", "left"]: return False
        return True
    except: return False

# --- HANDLERS ---
@app.on_message(filters.command("start") & filters.private)
async def start(c, m):
    uid = m.from_user.id
    if not await users.find_one({"user_id": uid}):
        await users.insert_one({"user_id": uid, "referrals": 0})
        if len(m.command) > 1 and m.command[1].isdigit():
            ref_id = int(m.command[1])
            if ref_id != uid:
                await users.update_one({"user_id": ref_id}, {"$inc": {"referrals": 1}})
                try: await c.send_message(ref_id, "✅ **Naya Referral mila!**")
                except: pass

    u = await users.find_one({"user_id": uid})
    cfg = await config.find_one({"_id": "channels_list"})
    chans = cfg.get("list", []) if cfg else []
    kb = [[InlineKeyboardButton(f"📢 Join Channel {i+1}", url=ch['link'])] for i, ch in enumerate(chans)]
    kb.append([InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")])
    
    me = await c.get_me()
    await m.reply(f"👋 **नमस्ते {m.from_user.first_name}!**\n\nमूवी के लिए **5 रिफरल** और चैनल जॉइन करना ज़रूरी है।\n\n📊 स्कोर: **{u.get('referrals', 0)}/5**\n🔗 लिंक: `https://t.me/{me.username}?start={uid}`", reply_markup=InlineKeyboardMarkup(kb))

@app.on_message(filters.command("add_channel") & filters.user(ADMIN))
async def add(c, m):
    if len(m.command) < 3: return await m.reply("❌ `/add_channel username link`")
    ch_id = m.command[1].strip().replace("@", "")
    await config.update_one({"_id": "channels_list"}, {"$addToSet": {"list": {"id": ch_id, "link": m.command[2]}}}, upsert=True)
    await m.reply(f"✅ Channel `{ch_id}` set!")

@app.on_message(filters.command("clear_all") & filters.user(ADMIN))
async def clear(c, m):
    await config.delete_one({"_id": "channels_list"})
    await m.reply("🧹 **Database साफ़!**")

@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_link(c, m):
    if len(m.command) < 2: return await m.reply("❌ `/set link`")
    await config.update_one({"_id": "target"}, {"$set": {"link": m.text.split(None, 1)[1]}}, upsert=True)
    await m.reply("✅ **Target link set!**")

@app.on_callback_query(filters.regex("check"))
async def cb(c, q):
    if not await is_joined(q.from_user.id):
        return await q.answer("❌ पहले सभी चैनल जॉइन करें!", show_alert=True)
    u = await users.find_one({"user_id": q.from_user.id})
    if u and u.get("referrals", 0) >= 5:
        target = await config.find_one({"_id": "target"})
        link = target.get("link", "Set nahi hai") if target else "Set nahi hai"
        await q.message.edit_text(f"✅ **अनलॉक हो गया!**\n\nलिंक: {link}")
    else:
        await q.answer(f"⚠️ स्कोर: {u.get('referrals', 0)}/5", show_alert=True)

# --- START BOT ---
async def main():
    await start_web() # Ab ye function upar define hai
    async with app:
        logger.info("DV BOT ONLINE ✅")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
