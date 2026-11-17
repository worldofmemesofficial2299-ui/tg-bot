import asyncio
import logging
import os

from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))
SECRET = os.environ.get("WEBHOOK_SECRET")  # optional but recommended


# ---------- handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💬 New chat", callback_data="chat"),
                InlineKeyboardButton("📷 Media", callback_data="media"),
            ],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        ]
    )
    await update.message.reply_text("Welcome! Pick an option:", reply_markup=kb)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(f"You picked: {q.data}")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")


# ---------- health ----------
async def health(request):
    return web.Response(text="OK")


# ---------- webhook ----------
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
    server.router.add_get("/", health)
    server.router.add_get("/health", health)
    server.router.add_post("/webhook", webhook)

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
