from flask import Flask
import threading
import subprocess
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running ✅"

def run_bot():
    os.system("python bot.py")

if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    app.run(host="0.0.0.0", port=10000)
