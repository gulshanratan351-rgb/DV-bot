import os, asyncio
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

app = Client("dv_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["new_db"]
users = db["users"]
config = db["config"]

async def start_web():
    server = web.Application()
    server.router.add_get("/", lambda r: web.Response(text="Running ✅"))
    await web.TCPSite(web.AppRunner(server), "0.0.0.0", PORT).start()

# --- JOIN CHECK HELPER ---
async def is_joined(user_id):
    cfg = await config.find_one({"_id": "channels"})
    channels = cfg.get("list", []) if cfg else []
    for ch in channels:
        try:
            # ID को साफ़ करके चेक करना
            cid = int(str(ch['id']).replace(" ", ""))
            m = await app.get_chat_member(cid, user_id)
            if m.status not in ["member", "administrator", "creator"]: return False
        except: return False
    return True

# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start(c, m):
    uid = m.from_user.id
    if not await users.find_one({"user_id": uid}):
        await users.insert_one({"user_id": uid, "referrals": 0})
        args = m.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref = int(args[1])
            if ref != uid:
                await users.update_one({"user_id": ref}, {"$inc": {"referrals": 1}})
                try: await c.send_message(ref, "🎊 नया रिफरल मिला!")
                except: pass

    u = await users.find_one({"user_id": uid})
    cfg = await config.find_one({"_id": "channels"})
    chans = cfg.get("list", []) if cfg else []
    
    kb = [[InlineKeyboardButton(f"📢 Join Channel {i+1}", url=ch['link'])] for i, ch in enumerate(chans)]
    kb.append([InlineKeyboardButton("🔁 Check Status", callback_data="check")])
    
    me = await c.get_me()
    await m.reply(f"👋 नमस्ते!\n\nस्कोर: **{u['referrals']}/5**\nलिंक: `https://t.me/{me.username}?start={uid}`", reply_markup=InlineKeyboardMarkup(kb))

# --- ADMIN: ADD CHANNEL ---
@app.on_message(filters.command("add_channel") & filters.user(ADMIN))
async def add(c, m):
    args = m.text.split()
    if len(args) < 3: return await m.reply("❌ लिखें: `/add_channel ID LINK`")
    await config.update_one({"_id": "channels"}, {"$addToSet": {"list": {"id": args[1], "link": args[2]}}}, upsert=True)
    await m.reply("✅ चैनल जुड़ गया!")

@app.on_message(filters.command("clear_all") & filters.user(ADMIN))
async def clear(c, m):
    await config.delete_one({"_id": "channels"})
    await m.reply("🧹 साफ़!")

@app.on_callback_query(filters.regex("check"))
async def cb(c, q):
    if not await is_joined(q.from_user.id):
        return await q.answer("❌ पहले जॉइन करें!", show_alert=True)
    u = await users.find_one({"user_id": q.from_user.id})
    if u['referrals'] >= 5:
        await q.message.edit_text("✅ मिशन पूरा! लिंक यहाँ है।")
    else:
        await q.answer(f"⚠️ स्कोर: {u['referrals']}/5", show_alert=True)

async def main():
    await start_web()
    async with app: await asyncio.Event().wait()

if __name__ == "__main__": asyncio.run(main())
    
