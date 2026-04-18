"""
FitStack AI - FastAPI Web Server
Handles OAuth flows, user signup, chat API, and serves the React frontend
"""

import os
import json
import secrets
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import init_db, get_db, User, UserTokens, Conversation
from datetime import datetime
from claude_chat import ClaudeChat
from fitness_data import FitnessDataCollector

app = FastAPI()

BASE_URL = "https://fitstack-ai.up.railway.app"
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# In-memory state store for OAuth flows (maps state -> telegram_id)
oauth_states = {}

claude = ClaudeChat()


@app.on_event("startup")
def startup():
    init_db()
    
@app.get("/")
def root():
    with open("onboarding.html") as f:
        return HTMLResponse(f.read())

# ─── CHAT API ────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    telegram_id = str(data.get("telegram_id", "")).strip()
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not telegram_id or not message:
        raise HTTPException(status_code=400, detail="telegram_id and message required")

    tokens = db.query(UserTokens).filter_by(telegram_id=telegram_id).first()
    if not tokens:
        raise HTTPException(status_code=404, detail="User not found")

    def save_whoop_token(uid, new_token):
        t = db.query(UserTokens).filter_by(telegram_id=uid).first()
        if t:
            t.whoop_refresh_token = new_token
            db.commit()

    collector = FitnessDataCollector(telegram_id, tokens, save_whoop_token)
    fitness_data = await collector.get_all_data()

    # Build conversation history for Claude
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": message})

    response_text = await claude.chat(messages, fitness_data)

    # Save conversation to DB
    convo = db.query(Conversation).filter_by(telegram_id=telegram_id).first()
    if not convo:
        convo = Conversation(telegram_id=telegram_id, messages=json.dumps([]))
        db.add(convo)

    existing = json.loads(convo.messages or "[]")
    existing.append({"role": "user", "content": message})
    existing.append({"role": "assistant", "content": response_text})
    convo.messages = json.dumps(existing[-40:])  # keep last 20 exchanges
    convo.updated_at = datetime.utcnow()
    db.commit()

    return {"text": response_text}


@app.get("/api/daily-summary/{telegram_id}")
async def daily_summary(telegram_id: str, db: Session = Depends(get_db)):
    tokens = db.query(UserTokens).filter_by(telegram_id=telegram_id).first()
    if not tokens:
        raise HTTPException(status_code=404, detail="User not found")

    def save_whoop_token(uid, new_token):
        t = db.query(UserTokens).filter_by(telegram_id=uid).first()
        if t:
            t.whoop_refresh_token = new_token
            db.commit()

    collector = FitnessDataCollector(telegram_id, tokens, save_whoop_token)
    fitness_data = await collector.get_all_data()

    whoop = fitness_data.get("whoop", {})
    strava = fitness_data.get("strava", {})
    hevy = fitness_data.get("hevy", {})

    today = whoop.get("today", {})

    # Last run
    runs = [a for a in strava.get("recent_activities", []) if a.get("type") == "Run"]
    last_run = None
    if runs:
        r = runs[0]
        pace = r.get("pace_min_per_mile")
        if pace:
            mins = int(pace)
            secs = int((pace - mins) * 60)
            pace_str = f"{mins}:{secs:02d}/mi"
        else:
            pace_str = "—"
        last_run = f"{r.get('distance_miles', 0)}mi · {pace_str}"

    # Last lift
    workouts = hevy.get("recent_workouts", [])
    last_lift = None
    if workouts:
        w = workouts[0]
        last_lift = f"{w.get('title', 'Workout')} · {w.get('date', '')}"

    return {
        "recovery": today.get("recovery_score"),
        "hrv": today.get("hrv_rmssd_milli"),
        "strain": None,  # pulled from cycle records if needed
        "sleep": today.get("sleep_performance_percentage"),
        "resting_hr": today.get("resting_heart_rate"),
        "last_run": last_run,
        "last_lift": last_lift,
    }


@app.get("/api/conversation/{telegram_id}")
async def get_conversation(telegram_id: str, db: Session = Depends(get_db)):
    convo = db.query(Conversation).filter_by(telegram_id=telegram_id).first()
    if not convo:
        return {"messages": []}
    return {"messages": json.loads(convo.messages or "[]")}


# ─── ONBOARDING API ──────────────────────────────────────────────────────────

@app.post("/api/start-signup")
async def start_signup(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    telegram_id = str(data.get("telegram_id", "")).strip()

    if not telegram_id:
        raise HTTPException(status_code=400, detail="Telegram ID required")

    existing = db.query(UserTokens).filter_by(telegram_id=telegram_id).first()
    if not existing:
        tokens = UserTokens(telegram_id=telegram_id)
        db.add(tokens)
        db.commit()

    return {"status": "ok", "user_id": telegram_id}


@app.post("/api/save-hevy-key")
async def save_hevy_key(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    telegram_id = data.get("user_id")
    hevy_key = data.get("hevy_api_key", "").strip()

    tokens = db.query(UserTokens).filter_by(telegram_id=telegram_id).first()
    if not tokens:
        raise HTTPException(status_code=404, detail="User not found")

    tokens.hevy_api_key = hevy_key
    tokens.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "ok"}


@app.post("/api/finish-signup")
async def finish_signup(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    telegram_username = data.get("user_id")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": f"@{telegram_username}",
                "text": (
                    "🎉 Welcome to FitStack AI!\n\n"
                    "Your personal fitness AI is ready. Try asking:\n"
                    "• \"How's my recovery today?\"\n"
                    "• \"What should I train?\"\n"
                    "• \"How's my training been this week?\"\n\n"
                    "📸 Send me a photo of food for nutrition estimates!\n\n"
                    "Use /help anytime to see what I can do."
                )
            }
        )
        result = resp.json()
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail="Could not send Telegram message.")

    return {"status": "ok"}


# ─── WHOOP OAUTH ─────────────────────────────────────────────────────────────

@app.get("/auth/whoop/start")
def whoop_auth_start(user_id: str):
    state = secrets.token_urlsafe(16)
    oauth_states[state] = user_id

    auth_url = (
        f"https://api.prod.whoop.com/oauth/oauth2/auth"
        f"?client_id={WHOOP_CLIENT_ID}"
        f"&redirect_uri={BASE_URL}/auth/whoop/callback"
        f"&response_type=code"
        f"&scope=offline+read:recovery+read:cycles+read:workout+read:sleep+read:profile+read:body_measurement"
        f"&state={state}"
    )
    return RedirectResponse(auth_url)


@app.get("/auth/whoop/callback")
async def whoop_callback(code: str, state: str, db: Session = Depends(get_db)):
    telegram_id = oauth_states.pop(state, None)
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.prod.whoop.com/oauth/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{BASE_URL}/auth/whoop/callback",
                "client_id": WHOOP_CLIENT_ID,
                "client_secret": WHOOP_CLIENT_SECRET,
            }
        )
        token_data = resp.json()

    if "refresh_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Whoop error: {token_data}")

    tokens = db.query(UserTokens).filter_by(telegram_id=telegram_id).first()
    if not tokens:
        tokens = UserTokens(telegram_id=telegram_id)
        db.add(tokens)

    tokens.whoop_refresh_token = token_data["refresh_token"]
    tokens.updated_at = datetime.utcnow()
    db.commit()

    return HTMLResponse("""
        <html><body style="font-family:sans-serif;text-align:center;padding:3rem;">
        <h2>✅ Whoop connected!</h2>
        <p>You can close this tab and return to FitStack.</p>
        <script>window.close();</script>
        </body></html>
    """)


# ─── STRAVA OAUTH ────────────────────────────────────────────────────────────

@app.get("/auth/strava/start")
def strava_auth_start(user_id: str):
    state = secrets.token_urlsafe(16)
    oauth_states[state] = user_id

    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri={BASE_URL}/auth/strava/callback"
        f"&response_type=code"
        f"&scope=read,activity:read_all"
        f"&approval_prompt=force"
        f"&state={state}"
    )
    return RedirectResponse(auth_url)


@app.get("/auth/strava/callback")
async def strava_callback(code: str, state: str, db: Session = Depends(get_db)):
    telegram_id = oauth_states.pop(state, None)
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            }
        )
        token_data = resp.json()

    if "refresh_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Strava error: {token_data}")

    tokens = db.query(UserTokens).filter_by(telegram_id=telegram_id).first()
    if not tokens:
        tokens = UserTokens(telegram_id=telegram_id)
        db.add(tokens)

    tokens.strava_refresh_token = token_data["refresh_token"]
    tokens.updated_at = datetime.utcnow()
    db.commit()

    return HTMLResponse("""
        <html><body style="font-family:sans-serif;text-align:center;padding:3rem;">
        <h2>✅ Strava connected!</h2>
        <p>You can close this tab and return to FitStack.</p>
        <script>window.close();</script>
        </body></html>
    """)


# ─── SERVE REACT FRONTEND ────────────────────────────────────────────────────
# This must come LAST — it catches all routes not matched above
# Run `npm run build` in the frontend folder first, then copy dist/ here

@app.get("/chat")
@app.get("/chat/{path:path}")
def serve_chat(path: str = ""):
    return HTMLResponse(open("dist/index.html").read())

if os.path.exists("dist"):
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
