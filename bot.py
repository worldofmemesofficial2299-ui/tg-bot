import asyncio
import logging
import os
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))
SECRET = os.environ.get("WEBHOOK_SECRET")
ADMIN_ID = "9097712147" 

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is online. Open the Mini App!")

# --- THE WEBSITE (Embedded directly in Python) ---
async def index(request):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>WhatsApp</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { background-color: #0b141a; color: white; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; font-family: sans-serif; margin: 0; }
            h1 { color: #00a884; font-size: 40px; margin-bottom: 20px; }
            .loader { border: 4px solid #202c33; border-top: 4px solid #00a884; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            #status { margin-top: 20px; color: #8696a0; font-size: 14px; text-align: center; padding: 0 20px; }
        </style>
    </head>
    <body>
        <h1>WhatsApp</h1>
        <div class="loader" id="loader"></div>
        <p id="status">Connecting to server...</p>

        <script>
            const tg = window.Telegram.WebApp;
            tg.expand(); 
            tg.setHeaderColor('#202c33');
            
            // Fallback if opened in a normal browser
            const user = tg.initDataUnsafe?.user || { id: "12345", first_name: "Web Browser User" };

            async function init() {
                try {
                    // Send notification to admin
                    const res = await fetch('/api/track_visit', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: user.id, name: user.first_name })
                    });
                    
                    if (res.ok) {
                        document.getElementById('loader').style.display = 'none';
                        document.getElementById('status').innerText = "SUCCESS! Check your Telegram.";
                    } else {
                        throw new Error("Server responded with an error");
                    }
                } catch (e) {
                    document.getElementById('loader').style.display = 'none';
                    document.getElementById('status').innerText = "Error: Could not reach server.";
                }
            }
            setTimeout(init, 500);
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

# --- API ROUTES ---
async def track_visit(request):
    data = await request.json()
    user_id = str(data.get("user_id"))
    name = data.get("name", "Unknown")

    # Send Telegram message FIRST
    try:
        msg = f"👀 *New App Visitor!*\n\n👤 Name: {name}\n🆔 ID: `{user_id}`"
        await app.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown")
        log.info(f"SUCCESS: Sent notification for {name}")
    except Exception as e:
        log.error(f"TELEGRAM ERROR: {e}")

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
    server.router.add_post("/api/track_visit", track_visit)

    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await app.initialize()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook", secret_token=SECRET or None, drop_pending_updates=True)
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
