import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os, threading, re

# ==========================================
# ⚙️ CONFIGURATION & SECRETS
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
WEB_APP_URL = os.environ.get("WEB_APP_URL") 
ADMIN_ID = 8718760365 
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "-1000000000000"))

# 🔴 Force Join Channels (Apne channels ke username yaha dalein)
CHANNEL_1 = os.environ.get("CHANNEL_1", "@errorkids")
CHANNEL_2 = os.environ.get("CHANNEL_2", "@ER_INSTAUPDATE")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# 🚧 Maintenance Flag
MAINTENANCE_MODE = False

from pymongo import MongoClient
MONGO_URI = os.environ.get("MONGO_URI") 
client = MongoClient(MONGO_URI)
db = client['bseb_video_db'] 
db_collection = db['app_data']

def load_db():
    doc = db_collection.find_one({"_id": "aliesn_data"})
    if doc and "data" in doc: return doc["data"]
    return {"users": {}, "videos": []}

def save_db(db_data):
    db_collection.update_one({"_id": "aliesn_data"}, {"$set": {"data": db_data}}, upsert=True)

db_data = load_db()
admin_states = {}

# ==========================================
# 🔒 SECURITY & VERIFICATION LOGIC
# ==========================================
def check_joined(user_id):
    if str(user_id) == str(ADMIN_ID): return True
    try:
        for ch in [CHANNEL_1, CHANNEL_2]:
            status = bot.get_chat_member(ch, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        print(f"Join check error: {e}")
        return False # Agar channel admin bot nahi hai, toh false return karega

@bot.message_handler(commands=['maintenance'])
def toggle_maintenance(m):
    global MAINTENANCE_MODE
    if str(m.from_user.id) != str(ADMIN_ID): return
    cmd = m.text.lower()
    if "on" in cmd:
        MAINTENANCE_MODE = True
        bot.reply_to(m, "🚧 **Maintenance Mode is now ON.**\nNormal users cannot access the bot.", parse_mode="Markdown")
    elif "off" in cmd:
        MAINTENANCE_MODE = False
        bot.reply_to(m, "✅ **Maintenance Mode is now OFF.**\nBot is live for everyone.", parse_mode="Markdown")
    else:
        bot.reply_to(m, f"Current Status: **{'ON 🔴' if MAINTENANCE_MODE else 'OFF 🟢'}**\nUse `/maintenance on` or `/maintenance off`", parse_mode="Markdown")

# ==========================================
# 🚀 START & FORCE JOIN FLOW
# ==========================================
@bot.message_handler(commands=['start'])
def start(m):
    global MAINTENANCE_MODE
    uid = str(m.from_user.id)
    
    if MAINTENANCE_MODE and uid != str(ADMIN_ID):
        return bot.send_message(m.chat.id, "🚧 <b>BOT IS UNDER MAINTENANCE</b> 🚧\n\nUpdate chal raha hai, kripya kuch samay baad try karein.", parse_mode="HTML")

    if uid not in db_data['users']:
        db_data['users'][uid] = {"name": m.from_user.first_name}
        save_db(db_data)
        
    if not check_joined(m.from_user.id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}"))
        markup.add(InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}"))
        markup.add(InlineKeyboardButton("✅ Verify & Continue", callback_data="verify_join"))
        
        bot.send_message(m.chat.id, "🔒 <b>Access Denied!</b>\n\nTo use Aliesn Batch, please join our official channels first.", reply_markup=markup, parse_mode="HTML")
        return
        
    send_webapp_menu(m.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_callback(call):
    if check_joined(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Verification Successful!")
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("▶️ ENTER ALIESN BATCH 🍿", web_app=WebAppInfo(url=WEB_APP_URL)))
        
        # 🧹 Edit message to keep chat clean
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id,
            text="🚀 <b>Welcome to Aliesn Batch!</b>\n\nEkdum HD aur bina buffering ke lectures dekho!",
            reply_markup=markup,
            parse_mode="HTML"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Please join all channels first!", show_alert=True)

def send_webapp_menu(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("▶️ ENTER ALIESN BATCH 🍿", web_app=WebAppInfo(url=WEB_APP_URL)))
    bot.send_message(chat_id, "🚀 <b>Welcome to Aliesn Batch!</b>\n\nEkdum HD aur bina buffering ke lectures dekho!", reply_markup=markup, parse_mode="HTML")

# ==========================================
# 📝 MEDIA HANDLERS & ADMIN COMMANDS (SAME AS BEFORE)
# ==========================================
@bot.message_handler(commands=['setpath'])
def set_path(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    path_str = m.text.replace('/setpath', '').strip()
    if not path_str: return bot.reply_to(m, "⚠️ Format: `/setpath Folder 1/Folder 2`", parse_mode="Markdown")
    admin_states.setdefault(m.from_user.id, {})['path'] = [p.strip() for p in path_str.split('/') if p.strip()]
    bot.reply_to(m, f"📂 **Path Ready:** `{' ➔ '.join(admin_states[m.from_user.id]['path'])}`", parse_mode="Markdown")

@bot.message_handler(commands=['rename'])
def rename_vid(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    if not m.reply_to_message: return bot.reply_to(m, "⚠️ Reply to a saved message!")
    new_title = m.text.replace('/rename', '').strip()
    reply_map = admin_states.get(m.from_user.id, {}).get('reply_map', {})
    if m.reply_to_message.message_id in reply_map:
        vid_info = reply_map[m.reply_to_message.message_id]
        for v in db_data.get('videos', []):
            if v.get('path') == vid_info['path']:
                for vid in v['data']:
                    if vid['url'] == vid_info['vid_url']:
                        vid['title'] = new_title
                        save_db(db_data)
                        return bot.reply_to(m, f"✅ Name updated: `{new_title}`", parse_mode="Markdown")

@bot.message_handler(content_types=['video', 'document'])
def handle_media(m):
    if str(m.from_user.id) != str(ADMIN_ID): return
    reply_map = admin_states.get(m.from_user.id, {}).get('reply_map', {})
    
    # Check if replying to attach PDF/DPP
    if m.reply_to_message and m.reply_to_message.message_id in reply_map:
        vid_info = reply_map[m.reply_to_message.message_id]
        copied_pdf = bot.copy_message(BIN_CHANNEL, m.chat.id, m.message_id)
        pdf_url = f"https://bot.local/{copied_pdf.message_id}/file.pdf"
        is_dpp = m.caption and '/dpp' in m.caption.lower()
        
        for v in db_data.get('videos', []):
            if v.get('path') == vid_info['path']:
                for vid in v['data']:
                    if vid['url'] == vid_info['vid_url']:
                        if is_dpp: vid['dpp'] = pdf_url
                        else: vid['pdf'] = pdf_url
                        save_db(db_data)
                        return bot.reply_to(m, f"✅ Attached Successfully!", parse_mode="Markdown")

    # Save new video
    target_path = admin_states.get(m.from_user.id, {}).get('path')
    if not target_path: return bot.reply_to(m, "❌ Pehle `/setpath` set karo!")
    
    try:
        copied_vid = bot.copy_message(BIN_CHANNEL, m.chat.id, m.message_id)
        vid_url = f"https://bot.local/{copied_vid.message_id}/video.mp4"
        raw_cap = m.caption if m.caption else (m.document.file_name if m.content_type=='document' else "Untitled")
        title = re.sub(r'http\S+|t\.me/\S+|@\w+', '', raw_cap.split('\n')[0]).replace('.mp4','').strip()
        
        doc_found = False
        if 'videos' not in db_data: db_data['videos'] = []
        for v in db_data['videos']:
            if v.get('path') == target_path:
                v.setdefault('data', []).append({"title": title, "url": vid_url, "pdf": "#", "dpp": "#"})
                doc_found = True; break
        if not doc_found:
            db_data['videos'].append({"path": target_path, "mode": "video", "data": [{"title": title, "url": vid_url, "pdf": "#", "dpp": "#"}]})
        save_db(db_data)
        
        reply_msg = bot.reply_to(m, f"✅ Saved: `{title}`\n_Reply with PDF for Notes. Reply with PDF + /dpp for DPP._", parse_mode="Markdown")
        admin_states.setdefault(m.from_user.id, {})['reply_map'] = admin_states.get(m.from_user.id, {}).get('reply_map', {})
        admin_states[m.from_user.id]['reply_map'][reply_msg.message_id] = {"path": target_path, "vid_url": vid_url}
    except Exception as e: bot.reply_to(m, f"Error: {e}")

# ==========================================
# 🌐 API ROUTES
# ==========================================
@app.route('/')
def index(): return render_template('index.html') 

@app.route('/api/get_data')
def get_data():
    tree = {}
    for doc in db_data.get('videos', []):
        path = doc.get('path', [])
        if not path: continue
        curr = tree
        for p in path[:-1]:
            if p not in curr: curr[p] = {}
            curr = curr[p]
        curr[path[-1]] = {"data": doc['data'], "mode": doc.get('mode', 'video')}
    return jsonify(tree)

@app.route('/api/admin/delete', methods=['POST'])
def delete_item():
    data = request.json
    if str(data.get('uid')) != str(ADMIN_ID): return jsonify({"error": "Not Admin!"})
    target = data.get('path', []) + [data.get('target')]
    db_data['videos'] = [v for v in db_data.get('videos', []) if not (v.get('path', [])[:len(target)] == target)]
    save_db(db_data)
    return jsonify({"status": "deleted"})

@app.route('/api/send_to_chat', methods=['POST'])
def send_to_chat():
    data = request.json
    uid = data.get('uid')
    url = data.get('url').replace("http://https://", "https://")
    
    caption = f"📚 **{data.get('title')}**\n📍 Type: {data.get('type').upper()}\n\n🔗 **View / Download Link:**\n[Open File]({url})\n\n*Downloaded via Aliesn Batch*"
    
    try:
        # 🔥 ANTI-SAVE & ANTI-FORWARD SECURITY (protect_content=True)
        bot.send_message(chat_id=uid, text=caption, parse_mode="Markdown", protect_content=True)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    t = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))))
    t.start()
    bot.infinity_polling()
