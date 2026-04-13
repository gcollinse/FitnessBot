"""
Fitness AI Telegram Bot
Connects Whoop, Hevy, and Strava with Claude AI
Supports photo analysis for nutrition estimation
"""

import os
import logging
import base64
import httpx
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
ALLOWED_USER_ID = os.getenv("ALLOWED_TELEGRAM_USER_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

collector = FitnessDataCollector()
claude = ClaudeChat()

conversation_histories = {}

# Daily nutrition log per user
nutrition_logs = {}


def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_ID:
        return True
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
        "📸 **Send me a photo of your food** and I'll estimate the nutrition!\n\n"
        "Ask me anything:\n"
        "• \"How's my recovery today?\"\n"
        "• \"Should I do a hard run today?\"\n"
        "• \"How has my training been this week?\"\n"
        "• /nutrition — see today's food log\n"
        "• /refresh — refresh your fitness data"
    )


async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    collector.clear_cache()
    await update.message.reply_text("✅ Data cache cleared! Fresh data on your next message.")


async def nutrition_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    user_id = update.effective_user.id
    log = nutrition_logs.get(user_id, [])

    if not log:
        await update.message.reply_text("No food logged today yet! Send me a photo of your meal to get started. 📸")
        return

    total_cal = sum(item.get("calories", 0) for item in log)
    total_protein = sum(item.get("protein_g", 0) for item in log)
    total_carbs = sum(item.get("carbs_g", 0) for item in log)
    total_fat = sum(item.get("fat_g", 0) for item in log)

    summary = f"🍽️ *Today's Nutrition Log*\n\n"
    for i, item in enumerate(log, 1):
        summary += f"{i}. {item['description']}\n"
        summary += f"   ~{item.get('calories', '?')} kcal | {item.get('protein_g', '?')}g protein\n\n"

    summary += f"─────────────────\n"
    summary += f"*Totals:*\n"
    summary += f"🔥 Calories: ~{total_cal} kcal\n"
    summary += f"💪 Protein: ~{total_protein}g\n"
    summary += f"🍞 Carbs: ~{total_carbs}g\n"
    summary += f"🥑 Fat: ~{total_fat}g"

    await update.message.reply_text(summary, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    user_id = update.effective_user.id
    await update.message.reply_text("📸 Analyzing your food... give me a sec!")

    # Get the highest resolution photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    # Download image as bytes
    async with httpx.AsyncClient() as client:
        resp = await client.get(file.file_path)
        image_bytes = resp.content

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Send to Claude with vision
    import aiohttp
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-opus-4-5",
                "max_tokens": 1024,
                "system": (
                    "You are a nutrition expert analyzing food photos. "
                    "Estimate calories and macros based on what you see. "
                    "Be practical and direct. State your assumptions about portion size. "
                    "Format your response as:\n"
                    "**[Food name]**\n"
                    "Estimated portion: ...\n"
                    "• Calories: ~X kcal\n"
                    "• Protein: ~Xg\n"
                    "• Carbs: ~Xg\n"
                    "• Fat: ~Xg\n\n"
                    "Brief note on accuracy/confidence.\n\n"
                    "Then at the end output a JSON block like this (for logging):\n"
                    "```json\n"
                    "{\"description\": \"...\", \"calories\": 0, \"protein_g\": 0, \"carbs_g\": 0, \"fat_g\": 0}\n"
                    "```"
                ),
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_b64
                                }
                            },
                            {
                                "type": "text",
                                "text": update.message.caption or "What's the nutritional breakdown of this meal?"
                            }
                        ]
                    }
                ]
            }
        )
        data = await resp.json()

    response_text = data["content"][0]["text"]

    # Try to extract and log the JSON nutrition data
    import json, re
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            nutrition_data = json.loads(json_match.group(1))
            if user_id not in nutrition_logs:
                nutrition_logs[user_id] = []
            nutrition_logs[user_id].append(nutrition_data)
            # Remove the JSON block from the displayed response
            response_text = response_text[:json_match.start()].strip()
            response_text += "\n\n✅ *Logged! Use /nutrition to see today's total.*"
        except Exception:
            pass

    await update.message.reply_text(response_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Sorry, you're not authorized.")
        return

    user_id = update.effective_user.id
    user_message = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    await update.message.reply_text("📊 Fetching your latest data...")
    fitness_data = await collector.get_all_data()

    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    # Include today's nutrition log in context if it exists
    if user_id in nutrition_logs and nutrition_logs[user_id]:
        fitness_data["nutrition_today"] = nutrition_logs[user_id]

    conversation_histories[user_id].append({"role": "user", "content": user_message})

    response = await claude.chat(
        conversation_history=conversation_histories[user_id],
        fitness_data=fitness_data
    )

    conversation_histories[user_id].append({"role": "assistant", "content": response})

    if len(conversation_histories[user_id]) > 20:
        conversation_histories[user_id] = conversation_histories[user_id][-20:]

    await update.message.reply_text(response)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refresh", refresh))
    app.add_handler(CommandHandler("nutrition", nutrition_summary))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
