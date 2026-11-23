#!/usr/bin/env python3
import os
import sys
import asyncio
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
OBF = os.path.join(HERE, "core")

if os.path.isdir(OBF):
    if OBF not in sys.path:
        sys.path.insert(0, OBF)
    try:
        from pytransform import pyarmor_runtime  # type: ignore
        pyarmor_runtime()
    except Exception:
        pass

from core import WormAi, Log
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ---- CONFIG ----
# Set TELEGRAM_BOT_TOKEN in the environment; never commit bot credentials.
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PROMPT_FILE = os.path.join(HERE, "system-prompt.txt")
DEFAULT_PROXY = os.getenv("WORM_PROXY") or os.getenv("GROK_PROXY", "")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Per-user conversation state store karne ke liye
user_sessions = {}
current_proxy = DEFAULT_PROXY
client = WormAi(current_proxy)

def get_system_prompt():
    try:
        if not os.path.exists(PROMPT_FILE):
            return ""
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        Log.Error(f"Failed to read system prompt: {e}")
        return ""

def ask_worm_ai(user_id: int, message: str):
    global client
    extra_data = user_sessions.get(user_id)

    if not extra_data:
        sp = get_system_prompt()
        extra_data = {"system_prompt": sp} if sp else None

    try:
        res = client.start_convo(message, extra_data=extra_data)
        if isinstance(res, dict):
            reply = res.get("response", "")
            user_sessions[user_id] = res.get("extra_data", extra_data)
            return reply
        return str(res)
    except Exception as e:
        Log.Error(f"Worm-Ai error: {e}")
        return f"❌ [Worm-Ai Error] {e}"

# ---- TELEGRAM HANDLERS ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)
    await update.message.reply_text(
        "🐛 *Worm-AI Online!*\n\n"
        "Apna prompt bhejo — main reply dunga.\n"
        "Commands:\n"
        "• `/restart` — Nayi chat shuru karne ke liye\n"
        "• `/proxy <url>` — Proxy set karne ke liye",
        parse_mode="Markdown"
    )

async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)
    await update.message.reply_text("🔄 *Conversation restarted!*", parse_mode="Markdown")

async def proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/proxy http://ip:port`", parse_mode="Markdown")
        return

    global current_proxy, client, user_sessions
    current_proxy = context.args[0].strip()
    client = WormAi(current_proxy)
    user_sessions.clear()
    await update.message.reply_text(f"✅ *Proxy set to:* `{current_proxy}`", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    status_msg = await update.message.reply_text("🧠 *Thinking...*", parse_mode="Markdown")

    loop = asyncio.get_running_loop()
    reply_text = await loop.run_in_executor(None, lambda: ask_worm_ai(user_id, prompt))

    if not reply_text:
        reply_text = "⚠️ Empty response from Worm-AI."

    await status_msg.delete()

    # Telegram 4096 characters limit ke hisaab se chunks mein bhejo
    for i in range(0, len(reply_text), 4000):
        await update.message.reply_text(reply_text[i:i + 4000])

# ---- MAIN ----
def main():
    if not BOT_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in the environment before starting the bot.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart_cmd))
    app.add_handler(CommandHandler("proxy", proxy_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Worm-AI Telegram Bot Online!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
