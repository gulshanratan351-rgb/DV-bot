import os
import secrets
from datetime import datetime, timezone, timedelta

from flask import Flask, request, jsonify, redirect, render_template_string
from pymongo import MongoClient
import telebot
from telebot import types

# =========================
# CONFIGURATION
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "").strip()
BASE_URL = os.getenv("BASE_URL", "").strip().rstrip("/")
ADMIN_ID = os.getenv("ADMIN_ID", "").strip() # Aapki Telegram ID
PORT = int(os.getenv("PORT", "10000"))

# Monetag Direct Links
TASK_LINKS = [
    "https://omg10.com/4/10904577",
    "https://omg10.com/4/10904579",
    "https://omg10.com/4/10904580",
    "https://omg10.com/4/10904581",
    "https://omg10.com/4/10904583",
]

# =========================
# INITIALIZATION
# =========================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

client = MongoClient(MONGO_URI)
db = client["task_unlock_bot"]
users_col = db["users"]
task_sessions_col = db["task_sessions"]
settings_col = db["settings"]

# =========================
# HELPERS
# =========================
def utc_now():
    return datetime.now(timezone.utc)

def get_unlock_link():
    """Database se current file link nikalne ke liye"""
    settings = settings_col.find_one({"id": "config"})
    if settings:
        return settings.get("unlock_url")
    return os.getenv("UNLOCK_FILE_URL", "https://t.me/your_channel")

def get_or_create_user(user_id, username="", first_name=""):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "tasks_completed": {"1": False, "2": False, "3": False, "4": False, "5": False},
            "created_at": utc_now()
        }
        users_col.insert_one(user)
    return user

def build_task_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    user_doc = users_col.find_one({"user_id": user_id})
    tasks = user_doc.get("tasks_completed", {})

    buttons = []
    for i in range(1, 6):
        status = "✅" if tasks.get(str(i)) else "🔗"
        token = secrets.token_urlsafe(16)
        task_sessions_col.insert_one({
            "token": token,
            "user_id": user_id,
            "task_no": str(i),
            "expires_at": utc_now() + timedelta(minutes=30)
        })
        url = f"{BASE_URL}/go/{token}"
        buttons.append(types.InlineKeyboardButton(f"Task {i} {status}", url=url))

    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("Verify Progress ✅", callback_data="verify_tasks"))
    markup.add(types.InlineKeyboardButton("Reset Tasks ♻️", callback_data="reset_tasks"))
    return markup

# =========================
# TELEGRAM HANDLERS
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    get_or_create_user(user_id, message.from_user.username, message.from_user.first_name)
    bot.send_message(
        message.chat.id,
        "👋 <b>Welcome!</b>\n\nFile unlock karne ke liye niche diye gaye 5 tasks pure karein.\n\n"
        "1️⃣ Task par click karein.\n2️⃣ 10 second wait karein.\n3️⃣ Bot par wapas aakar <b>Verify</b> dabayein.",
        reply_markup=build_task_keyboard(user_id)
    )

@bot.message_handler(commands=["setlink"])
def set_link(message):
    """Sirf admin naya link set kar sakta hai"""
    if str(message.from_user.id) != str(ADMIN_ID):
        bot.reply_to(message, "❌ You are not authorized.")
        return
    
    try:
        new_url = message.text.split(maxsplit=1)[1]
        settings_col.update_one({"id": "config"}, {"$set": {"unlock_url": new_url}}, upsert=True)
        bot.reply_to(message, f"✅ <b>New Link Updated!</b>\n\nAb users ko ye link milega:\n<code>{new_url}</code>")
    except:
        bot.reply_to(message, "⚠️ Usage: `/setlink https://yourlink.com`")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    user = users_col.find_one({"user_id": user_id})

    if call.data == "verify_tasks":
        done = sum(1 for v in user["tasks_completed"].values() if v)
        if done >= 5:
            final_link = get_unlock_link()
            bot.send_message(call.message.chat.id, f"🎉 <b>Success! All tasks done.</b>\n\nYour Link: {final_link}")
            bot.answer_callback_query(call.id, "Unlocked!")
        else:
            bot.answer_callback_query(call.id, f"❌ Sirf {done}/5 tasks complete hue hain!", show_alert=True)

    elif call.data == "reset_tasks":
        users_col.update_one({"user_id": user_id}, {"$set": {"tasks_completed": {"1": False, "2": False, "3": False, "4": False, "5": False}}})
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=build_task_keyboard(user_id))
        bot.answer_callback_query(call.id, "Tasks Reset Success.")

# =========================
# WEB ROUTES (WAIT PAGE)
# =========================

@app.route("/go/<token>")
def go_task(token):
    session = task_sessions_col.find_one({"token": token})
    if not session: return "<h1>Invalid or Expired Link</h1>", 400
    
    task_no = session["task_no"]
    target_ad_link = TASK_LINKS[int(task_no)-1]
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Verifying Task...</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; background: #f0f2f5; padding-top: 50px; }}
            .container {{ background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); display: inline-block; max-width: 90%; }}
            .timer {{ font-size: 40px; font-weight: bold; color: #007bff; margin: 20px 0; }}
            .btn {{ padding: 15px 40px; background: #28a745; color: white; border: none; border-radius: 10px; font-size: 20px; cursor: not-allowed; opacity: 0.5; text-decoration: none; transition: 0.3s; }}
            .btn.active {{ cursor: pointer; opacity: 1; box-shadow: 0 5px 15px rgba(40, 167, 69, 0.4); }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Task {task_no} of 5</h2>
            <p>Please wait for the timer to finish.</p>
            <div class="timer" id="timer">10</div>
            <form action="/complete/{token}" method="POST">
                <input type="hidden" name="ad_link" value="{target_ad_link}">
                <button id="mainBtn" type="submit" class="btn" disabled>Get Link</button>
            </form>
        </div>
        <script>
            let sec = 10;
            let countdown = setInterval(() => {{
                sec--;
                document.getElementById("timer").innerText = sec;
                if(sec <= 0) {{
                    clearInterval(countdown);
                    document.getElementById("timer").innerText = "Ready!";
                    let b = document.getElementById("mainBtn");
                    b.disabled = false; b.classList.add("active");
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/complete/<token>", methods=["POST"])
def complete(token):
    session = task_sessions_col.find_one({"token": token})
    if not session: return "Link Expired", 400
    
    # Mark task as completed for user
    users_col.update_one(
        {"user_id": session["user_id"]}, 
        {"$set": {f"tasks_completed.{session['task_no']}": True}}
    )
    # Session delete karein taaki reuse na ho
    task_sessions_col.delete_one({"token": token})
    
    return redirect(request.form.get("ad_link"))

# =========================
# WEBHOOK & RUN
# =========================

@app.route("/" + BOT_TOKEN, methods=["POST"])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=BASE_URL + "/" + BOT_TOKEN)
    return "Bot is running perfectly!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
    
