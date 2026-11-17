import asyncio
import logging
import os
import datetime
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))
SECRET = os.environ.get("WEBHOOK_SECRET")

# --- MongoDB Connection ---
MONGO_URI = "mongodb+srv://xDqHYfkWVKuFDRmX:fbfb80830_db_user@cluster0.65rr2ni.mongodb.net/?retryWrites=true&w=majority"
client = AsyncIOMotorClient(MONGO_URI)
db = client.whatsapp_clone
users_collection = db.users
messages_collection = db.messages

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Tap the 'Open WhatsApp' button on the bottom left to open the app.")

# --- Web App Handlers ---
async def index(request):
    path = os.path.join(os.path.dirname(__file__), "index.html")
    return web.FileResponse(path)

async def check_user(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({"registered": False})
    
    user = await users_collection.find_one({"telegram_id": str(user_id)})
    return web.json_response({"registered": bool(user)})

async def register_user(request):
    data = await request.json()
    user_id = str(data.get("user_id"))
    phone = data.get("phone")
    name = data.get("name")
    
    if user_id and phone:
        # Upsert (update or insert) the user
        await users_collection.update_one(
            {"telegram_id": user_id},
            {"$set": {"phone": phone, "name": name, "registered_at": datetime.datetime.now()}},
            upsert=True
        )
    return web.json_response({"status": "success"})

async def get_messages(request):
    user_id = request.query.get('user_id')
    chat_with = request.query.get('chat_with')
    if not user_id or not chat_with:
        return web.json_response([])
    
    # For now, we query by user_id and the "chat_with" dummy name
    cursor = messages_collection.find({"user_id": str(user_id), "chat_with": chat_with}).sort("_id", -1).limit(50)
    msgs = await cursor.to_list(length=50)
    msgs.reverse()
    
    formatted_msgs = [{"text": m.get("text"), "sender_id": m.get("sender_id"), "time": m.get("time", "")} for m in msgs]
    return web.json_response(formatted_msgs)

async def send_message(request):
    data = await request.json()
    user_id = str(data.get("user_id"))
    chat_with = data.get("chat_with")
    text = data.get("text")
    
    if user_id and text:
        time_now = datetime.datetime.now().strftime("%H:%M")
        await messages_collection.insert_one({
            "user_id": user_id,
            "chat_with": chat_with,
            "sender_id": user_id,
            "text": text,
            "time": time_now,
            "timestamp": datetime.datetime.now()
        })
        
        # Mocking a reply from the other person
        await asyncio.sleep(1) 
        await messages_collection.insert_one({
            "user_id": user_id,
            "chat_with": chat_with,
            "sender_id": "bot",
            "text": f"Got it! (Auto-reply)",
            "time": time_now,
            "timestamp": datetime.datetime.now()
        })
        
    return web.json_response({"status": "success"})

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
    
    # New API routes for Registration and App
    server.router.add_get("/api/check_user", check_user)
    server.router.add_post("/api/register", register_user)
    server.router.add_get("/api/messages", get_messages)
    server.router.add_post("/api/send", send_message)

    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook", secret_token=SECRET or None, drop_pending_updates=True)
    await app.start()

    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
