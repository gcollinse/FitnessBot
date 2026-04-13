"""
Claude Chat - Multi-user version
"""

import os
import json
import aiohttp
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MST = timezone(timedelta(hours=-6))

SYSTEM_PROMPT = """You are FitStack AI — a personal fitness AI assistant with access to real-time data from:
- *Whoop*: Recovery scores, HRV, resting heart rate, strain, sleep performance
- *Hevy*: Weightlifting workouts, exercises, sets, reps, weights
- *Strava*: Running activities, distances, paces, heart rate

Guidelines:
- Be conversational and direct — this is a personal chat
- Lead with the most relevant insight for their question
- Use specific numbers from their data
- Always use imperial units: pounds, miles, feet, Fahrenheit
- Calories in kcal, never kilojoules
- Pace in minutes per mile
- Format for Telegram — NO markdown tables, use simple bullet points
- Use *bold* (single asterisk) for important terms — never double asterisks
- If data is missing from a service, mention it briefly and work with what you have
- When recommending training intensity, always factor in Whoop recovery score
- Proactively mention cross-app patterns when relevant
- Keep responses concise unless they ask for detail

Today's date and time: {date}

Current fitness data:
{fitness_data}
"""


class ClaudeChat:
    def __init__(self):
        self.api_key = ANTHROPIC_API_KEY

    async def chat(self, conversation_history: list, fitness_data: dict) -> str:
        system = SYSTEM_PROMPT.format(
            date=datetime.now(tz=MST).strftime("%A, %B %d, %Y %I:%M %p MST"),
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
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1024,
                    "system": system,
                    "messages": conversation_history,
                }
            )
            data = await resp.json()

            if "error" in data:
                return f"Sorry, I hit an error: {data['error'].get('message', 'Unknown error')}"

            return data["content"][0]["text"]
