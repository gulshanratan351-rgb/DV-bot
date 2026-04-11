from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading, os

# ================= CONFIG =================
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME")  # without @

bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Running ✅"

# ================= DATABASE (simple dict) =================
links_db = {}          # user_id: link
channels = []          # required channels
referrals = {}         # user_id: count
referred_by = {}       # new_user: old_user

REQUIRED_REF = 5       # 🔥 required shares

# ================= START =================
@bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id

    # Referral system
    if len(message.command) > 1:
        ref_id = int(message.command[1])

        if user_id != ref_id:
            if user_id not in referred_by:
                referred_by[user_id] = ref_id
                referrals[ref_id] = referrals.get(ref_id, 0) + 1

    await message.reply_text(
        "👋 Welcome!\n\n"
        "🔐 Send /create <link>\n"
        "Example:\n/create https://mega.nz/file/abc123"
    )

# ================= ADD CHANNEL =================
@bot.on_message(filters.command("addchannel"))
async def add_channel(client, message):
    ch = message.text.split(" ")[1]
    channels.append(ch)
    await message.reply_text(f"✅ Added {ch}")

# ================= CREATE LINK =================
@bot.on_message(filters.command("create"))
async def create(client, message):
    try:
        link = message.text.split(" ")[1]
        user_id = message.from_user.id

        links_db[user_id] = link
        referrals[user_id] = 0  # reset count

        # 🔗 referral link
        share_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Check Access", callback_data="check")],
            [InlineKeyboardButton("📤 Share Link", url=share_link)]
        ])

        await message.reply_text(
            f"🔐 Link Locked!\n\n"
            f"📊 Required:\n"
            f"👉 Join all channels\n"
            f"👉 {REQUIRED_REF} users join via your link\n\n"
            f"📤 Share this link:\n{share_link}",
            reply_markup=btn
        )

    except:
        await message.reply_text("❌ Use: /create <link>")

# ================= CHECK ACCESS =================
@bot.on_callback_query()
async def check(client, query):
    user_id = query.from_user.id

    # 1️⃣ Check channels
    not_joined = []

    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(ch)
        except:
            not_joined.append(ch)

    if not_joined:
        btn = []
        for ch in not_joined:
            btn.append([InlineKeyboardButton(f"Join {ch}", url=f"https://t.me/{ch.replace('@','')}")])

        return await query.message.reply_text(
            "❌ पहले सभी चैनल join करो",
            reply_markup=InlineKeyboardMarkup(btn)
        )

    # 2️⃣ Check referrals
    count = referrals.get(user_id, 0)

    if count < REQUIRED_REF:
        return await query.message.reply_text(
            f"❌ अभी {count}/{REQUIRED_REF} users joined\n"
            f"📤 Share more!"
        )

    # 3️⃣ Unlock link
    link = links_db.get(user_id, "❌ Not Found")

    await query.message.reply_text(
        f"✅ Access Granted!\n\n🔗 {link}"
    )

# ================= RUN =================
def run_bot():
    bot.run()

threading.Thread(target=run_bot).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
