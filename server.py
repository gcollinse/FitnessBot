"""
FitStack AI - FastAPI Web Server
Handles OAuth flows, user signup, and serves the landing page
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

app = FastAPI()

BASE_URL = "https://fitstack-ai.up.railway.app"
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# In-memory state store for OAuth flows (maps state -> telegram_id)
oauth_states = {}


@app.on_event("startup")
def startup():
    init_db()


# ─── LANDING PAGE ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing_page():
    with open("index.html") as f:
        return f.read()


# ─── ONBOARDING API ──────────────────────────────────────────────────────────

@app.post("/api/start-signup")
async def start_signup(request: Request, db: Session = Depends(get_db)):
    """Called after Telegram Login Widget authorizes user"""
    data = await request.json()
    telegram_id = str(data.get("telegram_id", "")).strip()
    telegram_username = data.get("telegram_username", "").strip()
    name = data.get("name", "").strip()

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
    """Send the user a welcome message on Telegram"""
    data = await request.json()
    telegram_username = data.get("user_id")

    # Send welcome message via Telegram
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
            raise HTTPException(status_code=400, detail="Could not send Telegram message. Make sure you've started a chat with the bot first!")

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
