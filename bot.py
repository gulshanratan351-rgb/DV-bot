import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_async_engine import AsyncIOMotorClient

# Configurations
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
# चैनल आईडी की लिस्ट (e.g. [-100123, -100456])
CHANNELS = [int(x) for x in os.environ.get("CHANNELS", "").split(",")]
TARGET_LINK = os.environ.get("TARGET_LINK") # आपकी Short Link

db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.bot_database
users_col = db.users

bot = Client("ForceShareBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def is_subscribed(bot, user_id):
    for chat_id in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
        except:
            return False
    return True

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(bot, message):
    user_id = message.from_user.id
    referrer_id = message.command[1] if len(message.command) > 1 else None

    # Check Force Join
    if not await is_subscribed(bot, user_id):
        buttons = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/example")]] # यहाँ डायनामिक लिंक लगा सकते हैं
        return await message.reply("पहले हमारे सभी चैनल्स जॉइन करें!", reply_markup=InlineKeyboardMarkup(buttons))

    user_data = await users_col.find_one({"user_id": user_id})
    
    if not user_data:
        await users_col.insert_one({"user_id": user_id, "referred_by": referrer_id, "ref_count": 0})
        if referrer_id:
            await users_col.update_one({"user_id": int(referrer_id)}, {"$inc": {"ref_count": 1}})
            await bot.send_message(referrer_id, "किसी ने आपके लिंक से जॉइन किया है!")

    user_data = await users_col.find_one({"user_id": user_id})
    count = user_data.get("ref_count", 0)

    if count >= 5:
        await message.reply(f"बधाई हो! आपकी लिंक अनलॉक हो गई है:\n{TARGET_LINK}")
    else:
        ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
        await message.reply(
            f"लिंक अनलॉक करने के लिए 5 लोगों को इनवाइट करें।\n\n"
            f"अभी तक इनवाइट किए: {count}/5\n\n"
            f"आपका इनवाइट लिंक: {ref_link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Share Now", url=f"https://t.me/share/url?url={ref_link}") ]])
        )

bot.run()

