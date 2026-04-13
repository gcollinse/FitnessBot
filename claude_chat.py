"""
Claude Chat Integration
Sends fitness data + conversation history to Claude API
"""

import os
import json
import aiohttp
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """You are a personal fitness AI assistant with access to real-time data from three apps:
- **Whoop**: Recovery scores, HRV, resting heart rate, strain, sleep performance
- **Hevy**: Weightlifting workouts, exercises, sets, reps, weights
- **Strava**: Running activities, distances, paces, heart rate zones

Your job is to help the user understand their fitness data, spot patterns, give training recommendations, and answer questions about their health and performance.

User profile:
- Name: Grady
- Age: 21 years old
- Birthday: July 21
- Weight: 160 lbs
- Height: 5 foot 9 inches
- Current build: Muscle, visible abs, not completely shredded but pretty ripped
- Goals: Stay healthy all around, decent cardio, good lifting, as long as I look great on the beach
- Training experience: On and off running, lifting for 5ish years

Guidelines:
- Be conversational and direct — this is a personal chat, not a clinical report
- Lead with the most relevant insight for their question
- Use specific numbers from their data (e.g. "Your HRV was 67ms today, which is above your recent baseline")
- If data is missing or there's an error from a service, mention it briefly and work with what you have
- When recommending training intensity, always factor in Whoop recovery score
- Use emojis sparingly but naturally (✅ 📈 🔴 etc.)
- Keep responses concise unless they ask for detail
- If you notice interesting cross-app patterns (e.g. poor sleep → slower pace), proactively mention them
- Format responses for Telegram — avoid markdown tables, use simple bullet points instead
- Never use | table | format | — Telegram doesn't render them well
- Use plain dashes and line breaks for lists
- Always use imperial units: pounds (not kg), miles (not km), Fahrenheit (not Celsius)
- Calories burned in kcal (calories), never kilojoules
- Pace in minutes per mile, not per km
- Height in feet/inches, weight in pounds
- Use Telegram markdown formatting: *bold* for important terms and headers (single asterisk, not double)
- For extra emphasis use *bold* text — Telegram does not support underline, so just use bold for the most important things
- Never use ** double asterisks — Telegram renders * single asterisks as bold

Today's date: {date}

Current fitness data:
{fitness_data}
"""


class ClaudeChat:
    def __init__(self):
        self.api_key = ANTHROPIC_API_KEY

    async def chat(self, conversation_history: list, fitness_data: dict) -> str:
        system = SYSTEM_PROMPT.format(
            date=datetime.now(tz=timezone(timedelta(hours=-6))).strftime("%A, %B %d, %Y %I:%M %p MST"),
            fitness_data=json.dumps(fitness_data, indent=2, default=str)
        )

        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "system": system,
                    "messages": conversation_history,
                }
            )

            data = await resp.json()

            if "error" in data:
                logger.error(f"Claude API error: {data['error']}")
                return f"Sorry, I hit an error talking to Claude: {data['error'].get('message', 'Unknown error')}"

            return data["content"][0]["text"]
