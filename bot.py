import os, asyncio, logging
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web

# --- LOGGING (ताकि पता चले बोट क्या कर रहा है) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
ADMIN = int(os.environ.get("ADMIN_ID", "6158373752"))
PORT = int(os.environ.get("PORT", 8080))

# --- DATABASE ---
m_client = AsyncIOMotorClient(MONGO_URL)
db = m_client["DV_FINAL_PRO_DB"] # नया DB ताकि पुराने एरर खत्म हो जाएँ
users = db["users"]
config = db["config"]

app = Client("dv_movie_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER ---
async def start_web():
    server = web.Application()
    server.router.add_get("/", lambda r: web.Response(text="Bot is Running Stable ✅"))
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

# --- ⭐ ADVANCE JOIN CHECK (YE KABHI FAIL NAHI HOGA) ---
async def is_joined(user_id):
    try:
        cfg = await config.find_one({"_id": "channels_list"})
        chans = cfg.get("list", []) if cfg else []
        if not chans: return True

        for ch in chans:
            # ID/Username को साफ़ करना
            raw_id = str(ch['id']).strip().replace("@", "")
            try:
                # अगर ID है तो Integer, नहीं तो String
                target = int(raw_id) if raw_id.startswith("-") or raw_id.isdigit() else raw_id
                member = await app.get_chat_member(target, user_id)
                if member.status in ["kicked", "left"]: return False
            except errors.UserNotParticipant:
                return False
            except Exception as e:
                logger.error(f"Join Check Error for {raw_id}: {e}")
                return False
        return True
    except Exception:
        return False

# --- COMMANDS ---

@app.on_message(filters.command("start") & filters.private)
async def start(c, m):
    uid = m.from_user.id
    args = m.text.split()
    
    u_data = await users.find_one({"user_id": uid})
    if not u_data:
        await users.insert_one({"user_id": uid, "referrals": 0})
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != uid:
                await users.update_one({"user_id": ref_id}, {"$inc": {"referrals": 1}})
                try: await c.send_message(ref_id, "🎊 **बधाई हो! आपका नया रिफरल जुड़ा।**")
                except: pass

    u = await users.find_one({"user_id": uid})
    cfg = await config.find_one({"_id": "channels_list"})
    chans = cfg.get("list", []) if cfg else []
    
    kb = [[InlineKeyboardButton(f"📢 Join Channel {i+1}", url=ch['link'])] for i, ch in enumerate(chans)]
    kb.append([InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")])
    
    bot = await c.get_me()
    await m.reply(
        f"👋 **नमस्ते {m.from_user.first_name}!**\n\n"
        f"मूवी के लिए **5 रिफरल** और चैनल जॉइन करना ज़रूरी है।\n\n"
        f"📊 आपका स्कोर: **{u.get('referrals', 0)}/5**\n"
        f"🔗 लिंक: `https://t.me/{bot.username}?start={uid}`",
        reply_markup=InlineKeyboardMarkup(kb)
    )

@app.on_message(filters.command("add_channel") & filters.user(ADMIN))
async def add(c, m):
    args = m.text.split()
    if len(args) < 3: return await m.reply("❌ `/add_channel username_या_ID link`")
    
    ch_id = args[1].strip().replace("@", "")
    await config.update_one(
        {"_id": "channels_list"}, 
        {"$addToSet": {"list": {"id": ch_id, "link": args[2].strip()}}}, 
        upsert=True
    )
    await m.reply(f"✅ चैनल `{ch_id}` सेट!")

@app.on_message(filters.command("clear_all") & filters.user(ADMIN))
async def clear(c, m):
    await config.delete_one({"_id": "channels_list"})
    await m.reply("🧹 डेटाबेस साफ़!")

@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_link(c, m):
    args = m.text.split(None, 1)
    if len(args) < 2: return await m.reply("`/set link`")
    await config.update_one({"_id": "movie"}, {"$set": {"url": args[1]}}, upsert=True)
    await m.reply("✅ मूवी लिंक सेट!")

@app.on_callback_query(filters.regex("check"))
async def cb(c, q):
    if not await is_joined(q.from_user.id):
        return await q.answer("❌ पहले सभी चैनल जॉइन करें!", show_alert=True)
    
    u = await users.find_one({"user_id": q.from_user.id})
    if u and u.get("referrals", 0) >= 5:
        target = await config.find_one({"_id": "movie"})
        link = target.get("url", "Link not set") if target else "Link not set"
        await q.message.edit_text(f"✅ मिशन पूरा! लिंक यहाँ है:\n\n{link}")
    else:
        await q.answer(f"⚠️ स्कोर: {u.get('referrals', 0)}/5", show_alert=True)

async def main():
    await start_web()
    async with app:
        print("--- BOT IS ONLINE ---")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
