@app.route('/sms_webhook', methods=['GET', 'POST'])
def handle_sms():
    try:
        # SMS content nikalna
        sms_text = request.args.get('message', '').lower()
        if not sms_text and request.is_json:
            sms_text = request.json.get('message', '').lower()
        
        if not sms_text:
            return "EMPTY_SMS", 200

        # Admin ko SMS bhejna taaki pata chale webhook hit hua
        bot.send_message(ADMIN_ID, f"📩 **Incoming SMS Log:**\n`{sms_text}`")

        # Naya Solid Regex
        amount_match = re.search(r'(?:rs\.?|inr|amt)\s*([\d,]+\.\d{2})|([\d,]+\.\d{2})\s*(?:paid|received|deposited)', sms_text)

        if amount_match:
            amt = amount_match.group(1) or amount_match.group(2)
            amt = str(amt).replace(',', '') 
            
            # Database mein dhoondna
            pay_record = temp_pay_col.find_one({"amount": amt})
            
            if pay_record:
                uid = pay_record['user_id']
                mins = int(pay_record['mins'])
                fid = pay_record.get('fid')
                
                # Expiry Calculate aur Update
                exp = int((datetime.now() + timedelta(minutes=mins)).timestamp())
                users_col.update_one({"user_id": uid}, {"$set": {"expiry": exp}}, upsert=True)
                
                # Temp payment delete karna taaki timer ruk jaye
                temp_pay_col.delete_one({"_id": pay_record['_id']})
                
                # User ko confirmation
                bot.send_message(uid, "✅ **Payment Success!**\nAapka Prime subscription activate ho gaya hai.")
                
                # Agar koi file link pending tha toh wo bhejna
                if fid:
                    link_obj = links_col.find_one({"file_id": fid})
                    if link_obj:
                        bot.send_message(uid, f"🎁 **Aapka Link:**\n{link_obj['url']}")
                
                bot.send_message(ADMIN_ID, f"💰 **Auto-Approved:** User `{uid}` paid ₹{amt}")
                return "SUCCESS", 200
            else:
                bot.send_message(ADMIN_ID, f"⚠️ **Amount Match Hua (₹{amt})** par database mein ye amount kisi user ka nahi mila.")
        
        return "NO_MATCH", 200
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Webhook Error: {str(e)}")
        return "ERROR", 500
        
