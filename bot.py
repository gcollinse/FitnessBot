"""
Fitness AI Telegram Bot
Connects Whoop, Hevy, and Strava with Claude AI
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from fitness_data import FitnessDataCollector
from claude_chat import ClaudeChat

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_TELEGRAM_USER_ID")  # Your personal Telegram user ID

collector = FitnessDataCollector()
claude = ClaudeChat()

# Per-user conversation history
conversation_histories = {}


def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_ID:
        return True  # If not set, allow everyone (not recommended)
    return str(user_id) == ALLOWED_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you're not authorized to use this bot.")
        return

    await update.message.reply_text(
        "👋 Hey! I'm your personal fitness AI.\n\n"
        "I have access to your:\n"
        "• 💪 Whoop recovery & strain data\n"
        "• 🏋️ Hevy lifting history\n"
        "• 🏃 Strava running data\n\n"
        "Just ask me anything! Examples:\n"
        "• \"How's my recovery today?\"\n"
        "• \"Should I do a hard run today?\"\n"
        "• \"How has my training been this week?\"\n"
        "• \"What patterns do you see in my data?\"\n\n"
        "Use /refresh to force a data refresh."
    )


async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 Refreshing your fitness data...")
    collector.clear_cache()
    await msg.edit_text("✅ Data cache cleared! Your next message will fetch fresh data.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you're not authorized.")
        return

    user_id = update.effective_user.id
    user_message = update.message.text

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Initialize conversation history for this user
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    # Fetch fitness data (cached for 30 mins)
    await update.message.reply_text("📊 Fetching your latest data...")
    fitness_data = await collector.get_all_data()

    # Add user message to history
    conversation_histories[user_id].append({
        "role": "user",
        "content": user_message
    })

    # Get response from Claude
    response = await claude.chat(
        conversation_history=conversation_histories[user_id],
        fitness_data=fitness_data
    )

    # Add assistant response to history
    conversation_histories[user_id].append({
        "role": "assistant",
        "content": response
    })

    # Keep conversation history manageable (last 20 messages)
    if len(conversation_histories[user_id]) > 20:
        conversation_histories[user_id] = conversation_histories[user_id][-20:]

    await update.message.reply_text(response)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refresh", refresh))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
