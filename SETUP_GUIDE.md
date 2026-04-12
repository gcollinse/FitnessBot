# 🏋️ Fitness AI Telegram Bot — Setup Guide

A personal AI assistant that connects Whoop, Hevy, and Strava,
accessible via Telegram chat powered by Claude.

---

## What You'll Need (gather these first)

| Service | What to get | Where |
|---------|-------------|-------|
| Telegram | Bot token + your user ID | @BotFather in Telegram |
| Anthropic | API key | console.anthropic.com |
| Whoop | Client ID + Client Secret | developer.whoop.com |
| Strava | Client ID + Client Secret | strava.com/settings/api |
| Hevy | API key | Hevy app → Settings → API |

---

## Step 1 — Telegram Setup

### Create your bot
1. Open Telegram, search for **@BotFather**
2. Send: `/newbot`
3. Choose a name (e.g. "My Fitness AI") and username (e.g. `myfitness_ai_bot`)
4. Copy the **bot token** — looks like `7123456789:AAHdqTcvCHhvGgnuxxx`

### Find your Telegram User ID
1. Search for **@userinfobot** in Telegram
2. Send it any message
3. It replies with your user ID number — copy it

---

## Step 2 — API Credentials

### Whoop
1. Go to https://developer.whoop.com
2. Sign in with your Whoop account
3. Create a new application
4. Set redirect URI to: `http://localhost:8888/callback`
5. Copy your **Client ID** and **Client Secret**

### Strava
1. Go to https://www.strava.com/settings/api
2. Create an application
3. Set "Authorization Callback Domain" to: `localhost`
4. Copy your **Client ID** and **Client Secret**

### Hevy
1. Open the Hevy app on your phone
2. Go to Settings → Account (requires Hevy Pro)
3. Scroll to find "API Key" — copy it
> ⚠️ If you don't have a Hevy API key, the bot will still work with Whoop + Strava.
> You can manually add workout summaries to the conversation if needed.

---

## Step 3 — Local Setup (one-time)

You need Python installed. If you don't have it:
- Mac: Install from https://www.python.org/downloads/
- Windows: Install from https://www.python.org/downloads/

### A. Download the bot files
Put all the bot files in a folder on your computer, e.g. `fitness-bot/`

### B. Install dependencies
Open Terminal (Mac) or Command Prompt (Windows) in that folder:
```
pip install -r requirements.txt
```

### C. Create your .env file
1. Copy `.env.example` to `.env`
2. Fill in everything EXCEPT the refresh tokens (those come next):
```
TELEGRAM_TOKEN=7123456789:AAHdqTcvCHhvGgnuxxx
ALLOWED_TELEGRAM_USER_ID=123456789
ANTHROPIC_API_KEY=sk-ant-...
WHOOP_CLIENT_ID=abc123
WHOOP_CLIENT_SECRET=def456
STRAVA_CLIENT_ID=12345
STRAVA_CLIENT_SECRET=xyz789
HEVY_API_KEY=your-hevy-key
```

### D. Get your OAuth refresh tokens
This is a one-time step that opens a browser to authorize the apps:
```
python setup_oauth.py
```

It will:
1. Open your browser for Whoop → log in → authorize
2. Print your `WHOOP_REFRESH_TOKEN` — copy it into `.env`
3. Open your browser for Strava → log in → authorize
4. Print your `STRAVA_REFRESH_TOKEN` — copy it into `.env`

---

## Step 4 — Test it locally

Make sure your `.env` is complete, then run:
```
python bot.py
```

Open Telegram, message your bot `/start` — it should respond!
Try asking "How's my recovery today?" to make sure data is flowing.

Press Ctrl+C to stop it when done testing.

---

## Step 5 — Deploy to Railway (so it runs 24/7)

Railway is free to start and doesn't require any server knowledge.

### A. Create a GitHub repository
1. Go to https://github.com and create a free account if you don't have one
2. Create a new repository (name it `fitness-bot` or similar)
3. Upload all your bot files to it (drag and drop in the GitHub web interface)
> ⚠️ Do NOT upload your `.env` file — keep that secret!

### B. Sign up for Railway
1. Go to https://railway.app
2. Sign in with GitHub

### C. Create a new project
1. Click "New Project"
2. Choose "Deploy from GitHub repo"
3. Select your `fitness-bot` repo

### D. Add your environment variables
1. Click on your service in Railway
2. Go to the "Variables" tab
3. Click "Add Variable" for each line in your `.env` file
   (copy each key and value one by one)

### E. Deploy
Railway will automatically deploy. Click "Deploy" if it doesn't start automatically.

Your bot is now running 24/7! 🎉

---

## Using Your Bot

Once running, open Telegram and chat with your bot:

**Example questions:**
- "How's my recovery today?"
- "Should I do a hard workout or rest?"
- "How has my running been this month?"
- "What's my best recent lift for bench press?"
- "Do you see any patterns between my sleep and performance?"
- "Compare this week's training to last week"

**Commands:**
- `/start` — shows welcome message
- `/refresh` — clears the data cache to force fresh data

---

## Troubleshooting

**Bot doesn't respond**
- Check Railway logs for error messages
- Make sure `TELEGRAM_TOKEN` is correct

**"Unauthorized" error**
- Make sure `ALLOWED_TELEGRAM_USER_ID` matches your actual Telegram user ID

**Whoop data missing**
- Refresh tokens expire if unused. Re-run `setup_oauth.py` to get a new one

**Strava data missing**
- Same as above — re-run `setup_oauth.py`

**Hevy data missing**
- Check that `HEVY_API_KEY` is set and that you have Hevy Pro

---

## Cost Estimate

| Service | Cost |
|---------|------|
| Railway | Free (up to 500 hrs/month) or ~$5/mo for always-on |
| Anthropic API | ~$0.01–0.05 per conversation |
| Everything else | Free |

For personal use, you'll likely spend under $5/month total.
