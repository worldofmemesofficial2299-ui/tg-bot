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
messages_collection = db.messages

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Tap the 'Open WhatsApp' button on the bottom left to open the app.")

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(f"You picked: {q.data}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")

# --- Web App (API & Frontend) Handlers ---
async def index(request):
    path = os.path.join(os.path.dirname(__file__), "index.html")
    return web.FileResponse(path)

async def health(request):
    return web.Response(text="OK")

async def get_messages(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response([])
    
    # Fetch last 50 messages from DB
    cursor = messages_collection.find({"user_id": str(user_id)}).sort("_id", -1).limit(50)
    msgs = await cursor.to_list(length=50)
    msgs.reverse() # Oldest to newest
    
    # Format for frontend
    formatted_msgs = []
    for m in msgs:
        formatted_msgs.append({
            "text": m.get("text"),
            "sender_id": m.get("sender_id"),
            "time": m.get("time", "")
        })
    return web.json_response(formatted_msgs)

async def send_message(request):
    data = await request.json()
    user_id = data.get("user_id")
    text = data.get("text")
    
    if user_id and text:
        time_now = datetime.datetime.now().strftime("%H:%M")
        
        # Save to MongoDB
        await messages_collection.insert_one({
            "user_id": str(user_id),
            "sender_id": str(user_id), # Sent by user
            "text": text,
            "time": time_now,
            "timestamp": datetime.datetime.now()
        })
        
        # Optional: Echo it back as a "received" message to simulate a chat
        await messages_collection.insert_one({
            "user_id": str(user_id),
            "sender_id": "bot",
            "text": f"Echo: {text}",
            "time": time_now,
            "timestamp": datetime.datetime.now()
        })
        
    return web.json_response({"status": "success"})

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
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    server = web.Application()
    server.router.add_get("/", index) # Serve the WhatsApp UI here
    server.router.add_get("/health", health)
    server.router.add_post("/webhook", webhook)
    server.router.add_get("/api/messages", get_messages)
    server.router.add_post("/api/send", send_message)

    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("HTTP server listening on %s", PORT)

    await app.initialize()
    await app.bot.set_webhook(
        f"{WEBHOOK_URL}/webhook",
        secret_token=SECRET or None,
        drop_pending_updates=True,
    )
    await app.start()
    log.info("Webhook registered at %s/webhook", WEBHOOK_URL)

    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
