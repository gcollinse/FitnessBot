"""
FitStack AI - Multi-user Telegram Bot
Looks up each user's tokens from PostgreSQL
"""

import os
import json
import base64
import logging
import httpx
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sqlalchemy.orm import Session
from database import SessionLocal, UserTokens, Conversation, User, init_db
from fitness_data_multi import FitnessDataCollector
from claude_chat_multi import ClaudeChat
from datetime import datetime

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

claude = ClaudeChat()
nutrition_logs = {}


def get_user_tokens(telegram_id: str):
    db = SessionLocal()
    try:
        return db.query(UserTokens).filter_by(telegram_id=str(telegram_id)).first()
    finally:
        db.close()


def get_conversation(telegram_id: str):
    db = SessionLocal()
    try:
        conv = db.query(Conversation).filter_by(telegram_id=str(telegram_id)).first()
        if conv:
            return json.loads(conv.messages)
        return []
    finally:
        db.close()


def save_conversation(telegram_id: str, messages: list):
    db = SessionLocal()
    try:
        conv = db.query(Conversation).filter_by(telegram_id=str(telegram_id)).first()
        if not conv:
            conv = Conversation(telegram_id=str(telegram_id))
            db.add(conv)
        conv.messages = json.dumps(messages[-20:])
        conv.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def save_whoop_token(telegram_id: str, new_token: str):
    db = SessionLocal()
    try:
        tokens = db.query(UserTokens).filter_by(telegram_id=str(telegram_id)).first()
        if tokens:
            tokens.whoop_refresh_token = new_token
            tokens.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or ""

    # Auto-register user if they message the bot directly
    db = SessionLocal()
    try:
        tokens = db.query(UserTokens).filter_by(telegram_id=user_id).first()
        # Also check by username (set during web signup)
        if not tokens and username:
            tokens = db.query(UserTokens).filter_by(telegram_id=username).first()
            if tokens:
                tokens.telegram_id = user_id
                db.commit()
    finally:
        db.close()

    await update.message.reply_text(
        "👋 Hey! I'm your FitStack AI.\n\n"
        "I can see your Whoop, Strava, and Hevy data.\n\n"
        "Just ask me anything:\n"
        "• \"How's my recovery today?\"\n"
        "• \"What should I train?\"\n"
        "• \"How's my week looking?\"\n\n"
        "📸 Send a food photo for nutrition estimates!\n\n"
        "/nutrition — today's food log\n"
        "/refresh — refresh data"
    )


async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    collector = FitnessDataCollector(user_id, None)
    collector.clear_cache()
    await update.message.reply_text("✅ Data refreshed!")


async def nutrition_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    log = nutrition_logs.get(user_id, [])

    if not log:
        await update.message.reply_text("No food logged today! Send me a photo of your meal. 📸")
        return

    total_cal = sum(item.get("calories", 0) for item in log)
    total_protein = sum(item.get("protein_g", 0) for item in log)
    total_carbs = sum(item.get("carbs_g", 0) for item in log)
    total_fat = sum(item.get("fat_g", 0) for item in log)

    summary = "*Today's Nutrition Log*\n\n"
    for i, item in enumerate(log, 1):
        summary += f"{i}. {item['description']}\n"
        summary += f"   ~{item.get('calories', '?')} kcal | {item.get('protein_g', '?')}g protein\n\n"
    summary += f"─────────────────\n"
    summary += f"*Totals:*\n"
    summary += f"Calories: ~{total_cal} kcal\n"
    summary += f"Protein: ~{total_protein}g\n"
    summary += f"Carbs: ~{total_carbs}g\n"
    summary += f"Fat: ~{total_fat}g"

    await update.message.reply_text(summary, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    await update.message.reply_text("📸 Analyzing your food...")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    async with httpx.AsyncClient() as client:
        resp = await client.get(file.file_path)
        image_bytes = resp.content

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "system": (
                    "You are a nutrition expert analyzing food photos. "
                    "Estimate calories and macros. Use imperial units (oz, lbs). "
                    "Be practical and direct. State portion size assumptions. "
                    "Format: *[Food name]*\nPortion: ...\nCalories: ~X kcal\nProtein: ~Xg\nCarbs: ~Xg\nFat: ~Xg\n\nBrief confidence note.\n\n"
                    "End with JSON block:\n```json\n{\"description\": \"...\", \"calories\": 0, \"protein_g\": 0, \"carbs_g\": 0, \"fat_g\": 0}\n```"
                ),
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                        {"type": "text", "text": update.message.caption or "Nutrition breakdown?"}
                    ]
                }]
            }
        )
        data = await resp.json()

    response_text = data["content"][0]["text"]

    import re
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            nutrition_data = json.loads(json_match.group(1))
            if user_id not in nutrition_logs:
                nutrition_logs[user_id] = []
            nutrition_logs[user_id].append(nutrition_data)
            response_text = response_text[:json_match.start()].strip()
            response_text += "\n\n✅ _Logged! Use /nutrition to see today's total._"
        except Exception:
            pass

    await update.message.reply_text(response_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_message = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    tokens = get_user_tokens(user_id)
    if not tokens:
        await update.message.reply_text(
            "Looks like you haven't set up FitStack yet!\n\n"
            "Visit https://fitstack-ai.up.railway.app to connect your apps."
        )
        return

    await update.message.reply_text("📊 Fetching your data...")

    collector = FitnessDataCollector(user_id, tokens, save_whoop_token_fn=save_whoop_token)
    fitness_data = await collector.get_all_data()

    if user_id in nutrition_logs and nutrition_logs[user_id]:
        fitness_data["nutrition_today"] = nutrition_logs[user_id]

    history = get_conversation(user_id)
    history.append({"role": "user", "content": user_message})

    response = await claude.chat(conversation_history=history, fitness_data=fitness_data)

    history.append({"role": "assistant", "content": response})
    save_conversation(user_id, history)

    await update.message.reply_text(response)


def main():
    init_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("refresh", refresh))
    app.add_handler(CommandHandler("nutrition", nutrition_summary))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("FitStack AI Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
