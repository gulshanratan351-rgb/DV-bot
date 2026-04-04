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
ADMIN = int(os.environ.get("ADMIN_ID", "6158373752")) # अपनी ID यहाँ पक्की करें
PORT = int(os.environ.get("PORT", 8080))

app = Client("dv_final_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["bot_database_v2"] # नया डेटाबेस नाम ताकि पुराना कचरा हट जाए
users = db["users"]
config = db["config"]

# --- WEB SERVER (Render को जगाए रखने के लिए) ---
async def start_web():
    server = web.Application()
    server.router.add_get("/", lambda r: web.Response(text="Bot is Running 100% ✅"))
    await web.TCPSite(web.AppRunner(server), "0.0.0.0", PORT).start()

# --- ⭐ JOIN CHECK (PUBLIC & PRIVATE FIXED) ---
async def is_joined(user_id):
    try:
        cfg = await config.find_one({"_id": "channels_list"})
        chans = cfg.get("list", []) if cfg else []
        if not chans: return True

        for ch in chans:
            # Username/ID को साफ़ करना (Space और @ हटाना)
            raw_id = str(ch['id']).strip().replace("@", "")
            try:
                # अगर ID नंबर है तो उसे Integer बनाना, नहीं तो Username रहने देना
                final_target = int(raw_id) if raw_id.startswith("-") or raw_id.isdigit() else raw_id
                
                member = await app.get_chat_member(final_target, user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    return False
            except Exception as e:
                print(f"Check Error for {raw_id}: {e}")
                return False # बोट एडमिन नहीं होगा तो भी False आएगा
        return True
    except Exception as e:
        print(f"Main Error: {e}")
        return False

# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start(c, m):
    uid = m.from_user.id
    args = m.text.split()
    
    # Referral & Registration
    user_data = await users.find_one({"user_id": uid})
    if not user_data:
        await users.insert_one({"user_id": uid, "referrals": 0})
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != uid:
                await users.update_one({"user_id": ref_id}, {"$inc": {"referrals": 1}})
                try: await c.send_message(ref_id, "🎊 **बधाई हो! एक नया रिफरल मिला।**")
                except: pass

    u = await users.find_one({"user_id": uid})
    cfg = await config.find_one({"_id": "channels_list"})
    chans = cfg.get("list", []) if cfg else []
    
    kb = [[InlineKeyboardButton(f"📢 Join Channel {i+1}", url=ch['link'])] for i, ch in enumerate(chans)]
    kb.append([InlineKeyboardButton("🔁 Check Status / Unlock", callback_data="check")])
    
    me = await c.get_me()
    await m.reply(
        f"👋 **नमस्ते {m.from_user.first_name}!**\n\n"
        f"मूवी लिंक के लिए **5 रिफरल** और चैनल जॉइन करना ज़रूरी है।\n\n"
        f"📊 आपका स्कोर: **{u.get('referrals', 0)}/5**\n"
        f"🔗 रिफरल लिंक: `https://t.me/{me.username}?start={uid}`",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# --- ADMIN COMMANDS ---

@app.on_message(filters.command("add_channel") & filters.user(ADMIN))
async def add(c, m):
    args = m.text.split()
    if len(args) < 3: return await m.reply("❌ सही तरीका: `/add_channel username_या_ID link`")
    
    ch_id = args[1].strip().replace("@", "")
    ch_link = args[2].strip()
    
    await config.update_one(
        {"_id": "channels_list"}, 
        {"$addToSet": {"list": {"id": ch_id, "link": ch_link}}}, 
        upsert=True
    )
    await m.reply(f"✅ **चैनल `{ch_id}` सेट हो गया!**")

@app.on_message(filters.command("clear_all") & filters.user(ADMIN))
async def clear(c, m):
    await config.delete_one({"_id": "channels_list"})
    await m.reply("🧹 **डेटाबेस साफ़!** अब नए सिरे से /add_channel करें।")

@app.on_message(filters.command("set") & filters.user(ADMIN))
async def set_link(c, m):
    args = m.text.split(None, 1)
    if len(args) < 2: return await m.reply("Usage: `/set link`")
    await config.update_one({"_id": "target"}, {"$set": {"link": args[1]}}, upsert=True)
    await m.reply("✅ **मूवी लिंक सेट हो गया!**")

# --- CHECK BUTTON ---
@app.on_callback_query(filters.regex("check"))
async def cb(c, q):
    if not await is_joined(q.from_user.id):
        return await q.answer("❌ पहले सभी चैनल जॉइन करें!", show_alert=True)
    
    u = await users.find_one({"user_id": q.from_user.id})
    if u and u.get("referrals", 0) >= 5:
        target = await config.find_one({"_id": "target"})
        link = target.get("link", "Link not set") if target else "Link not set"
        await q.message.edit_text(f"✅ **अनलॉक हो गया!**\n\nलिंक: {link}")
    else:
        await q.answer(f"⚠️ स्कोर: {u.get('referrals', 0)}/5 | 5 पूरे करें!", show_alert=True)

# --- START BOT ---
async def main():
    await start_web()
    async with app:
        print("--- BOT IS ONLINE SUCCESSFULLY ---")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
