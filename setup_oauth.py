"""
One-time OAuth setup script for Whoop and Strava.
Run this locally ONCE to get your refresh tokens, then add them to .env
"""

import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from dotenv import load_dotenv

load_dotenv()


# ─── CONFIG ───────────────────────────────────────
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

REDIRECT_URI = "http://localhost:8888/callback"
PORT = 8888

captured_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global captured_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        captured_code = params.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Got it! You can close this tab.</h2>")

    def log_message(self, format, *args):
        pass  # Suppress server logs


def get_code(auth_url):
    global captured_code
    captured_code = None
    webbrowser.open(auth_url)
    print(f"\n  Opening browser... If it doesn't open, go to:\n  {auth_url}\n")

    server = HTTPServer(("localhost", PORT), CallbackHandler)
    server.handle_request()
    return captured_code


def setup_whoop():
    print("\n" + "="*50)
    print("  WHOOP SETUP")
    print("="*50)

    if not WHOOP_CLIENT_ID:
        print("  ⚠️  WHOOP_CLIENT_ID not set in .env — skipping")
        return

    auth_url = (
        f"https://api.prod.whoop.com/oauth/oauth2/auth"
        f"?client_id={WHOOP_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=offline+read:recovery+read:cycles+read:workout+read:sleep+read:profile+read:body_measurement"
        f"&state=fitnessbotauth123"
    )

    code = get_code(auth_url)
    if not code:
        print("  ❌ No code received")
        return

    resp = requests.post(
        "https://api.prod.whoop.com/oauth/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": WHOOP_CLIENT_ID,
            "client_secret": WHOOP_CLIENT_SECRET,
        }
    )
    data = resp.json()

    if "refresh_token" in data:
        print(f"\n  ✅ Success! Add this to your .env:\n")
        print(f"  WHOOP_REFRESH_TOKEN={data['refresh_token']}\n")
    else:
        print(f"  ❌ Error: {data}")


def setup_strava():
    print("\n" + "="*50)
    print("  STRAVA SETUP")
    print("="*50)

    if not STRAVA_CLIENT_ID:
        print("  ⚠️  STRAVA_CLIENT_ID not set in .env — skipping")
        return

    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=read,activity:read_all"
        f"&approval_prompt=force"
    )

    code = get_code(auth_url)
    if not code:
        print("  ❌ No code received")
        return

    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        }
    )
    data = resp.json()

    if "refresh_token" in data:
        print(f"\n  ✅ Success! Add this to your .env:\n")
        print(f"  STRAVA_REFRESH_TOKEN={data['refresh_token']}\n")
    else:
        print(f"  ❌ Error: {data}")


if __name__ == "__main__":
    print("\n🏋️  Fitness Bot — One-Time OAuth Setup")
    print("This will open your browser twice (once for Whoop, once for Strava).")
    print("Just log in and authorize — the tokens will appear here.\n")

    input("Press Enter to start Whoop auth...")
    setup_whoop()

    input("\nPress Enter to start Strava auth...")
    setup_strava()

    print("\n✅ Done! Copy the tokens above into your .env file, then deploy.")
