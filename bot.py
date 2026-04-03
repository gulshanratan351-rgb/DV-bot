@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # यह सिर्फ सिंपल टेक्स्ट रिप्लाई देगा
    await message.reply(
        f"नमस्ते {message.from_user.first_name}!\n\n"
        "मैं एक ऑटो-रिप्लाई बॉट हूँ। अभी मैं टेस्टिंग मोड में हूँ। "
        "जल्द ही यहाँ आपको मूवी लिंक्स मिलेंगे! 🚀"
    )
    
