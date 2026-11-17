import asyncio
import logging
import os
import datetime
import aiohttp
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

# NODE BRIDGE URL (We will deploy this next)
BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://localhost:3000")

# --- MongoDB Connection (Fixed SSL) ---
MONGO_URI = "mongodb+srv://xDqHYfkWVKuFDRmX:fbfb80830_db_user@cluster0.65rr2ni.mongodb.net/?retryWrites=true&w=majority"
client = AsyncIOMotorClient(MONGO_URI)
db = client.whatsapp_clone
users_col = db.users
messages_col = db.messages
chats_col = db.chats

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Tap the 'Open WhatsApp' button on the bottom left.")

# --- Web App Handlers ---
async def index(request):
    path = os.path.join(os.path.dirname(__file__), "index.html")
    return web.FileResponse(path)

async def check_user(request):
    user_id = request.query.get('user_id')
    user = await users_col.find_one({"telegram_id": str(user_id)})
    return web.json_response({"registered": bool(user)})

async def register_user(request):
    data = await request.json()
    await users_col.update_one(
        {"telegram_id": str(data.get("user_id"))},
        {"$set": {"phone": data.get("phone"), "name": data.get("name"), "registered_at": datetime.datetime.now()}},
        upsert=True
    )
    return web.json_response({"status": "success"})

async def get_chats(request):
    user_id = request.query.get('user_id')
    # Fetch real chats from DB (synced from WhatsApp Bridge)
    cursor = chats_col.find({"user_id": str(user_id)})
    chats = await cursor.to_list(length=100)
    return web.json_response([{"name": c["name"], "last_message": c.get("last_message"), "time": c.get("time")} for c in chats])

async def get_messages(request):
    user_id = request.query.get('user_id')
    chat_with = request.query.get('chat_with')
    cursor = messages_col.find({"user_id": str(user_id), "chat_with": chat_with}).sort("_id", 1).limit(50)
    msgs = await cursor.to_list(length=50)
    return web.json_response([{"text": m["text"], "sender_id": m["sender_id"], "time": m["time"]} for m in msgs])

async def send_message(request):
    data = await request.json()
    user_id = str(data.get("user_id"))
    chat_with = data.get("chat_with")
    text = data.get("text")
    
    # 1. Save to DB
    await messages_col.insert_one({
        "user_id": user_id, "chat_with": chat_with, "sender_id": user_id,
        "text": text, "time": datetime.datetime.now().strftime("%H:%M")
    })
    
    # 2. Forward to WhatsApp Bridge
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(f"{BRIDGE_URL}/send", json={"to": chat_with, "text": text})
    except Exception as e:
        log.error(f"Bridge error: {e}")
        
    return web.json_response({"status": "success"})

async def link_device(request):
    data = await request.json()
    code = data.get("code")
    # Send code to Node Bridge to link WhatsApp
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(f"{BRIDGE_URL}/link", json={"code": code})
    except Exception as e:
        log.error(f"Bridge error: {e}")
    return web.json_response({"status": "success"})

# Receive messages FROM WhatsApp Bridge
async def whatsapp_webhook(request):
    data = await request.json()
    # Save WhatsApp message to MongoDB so Mini App can see it
    await messages_col.insert_one({
        "user_id": "MAIN_USER", "chat_with": data["from"], "sender_id": data["from"],
        "text": data["body"], "time": datetime.datetime.now().strftime("%H:%M")
    })
    # Update chat list
    await chats_col.update_one(
        {"user_id": "MAIN_USER", "name": data["from"]},
        {"$set": {"last_message": data["body"], "time": "Now"}},
        upsert=True
    )
    return web.json_response({"status": "ok"})

async def health(request):
    return web.Response(text="OK")

async def webhook(request):
    if SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET:
        return web.Response(status=403)
    data = await request.json()
    await app.update_queue.put(Update.de_json(data, app.bot))
    return web.Response()

async def main():
    global app
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))

    server = web.Application()
    server.router.add_get("/", index)
    server.router.add_get("/health", health)
    server.router.add_post("/webhook", webhook)
    server.router.add_get("/api/check_user", check_user)
    server.router.add_post("/api/register", register_user)
    server.router.add_get("/api/chats", get_chats)
    server.router.add_get("/api/messages", get_messages)
    server.router.add_post("/api/send", send_message)
    server.router.add_post("/api/link_device", link_device)
    server.router.add_post("/api/whatsapp-webhook", whatsapp_webhook)

    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook", secret_token=SECRET or None, drop_pending_updates=True)
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
