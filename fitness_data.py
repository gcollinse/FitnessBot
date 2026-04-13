"""
Fitness Data Collector
Fetches data from Whoop, Hevy, and Strava APIs
Uses Redis to persist rotating Whoop refresh token
"""
 
import os
import json
import time
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional
import logging
 
logger = logging.getLogger(__name__)
 
CACHE_DURATION = 30 * 60  # 30 minutes in seconds
 
 
class FitnessDataCollector:
    def __init__(self):
        self._cache = {}
        self._cache_time = {}
 
        # Whoop
        self.whoop_client_id = os.getenv("WHOOP_CLIENT_ID")
        self.whoop_client_secret = os.getenv("WHOOP_CLIENT_SECRET")
        self.whoop_refresh_token = os.getenv("WHOOP_REFRESH_TOKEN")
        self._whoop_access_token = None
 
        # Strava
        self.strava_client_id = os.getenv("STRAVA_CLIENT_ID")
        self.strava_client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.strava_refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        self._strava_access_token = None
 
        # Hevy
        self.hevy_api_key = os.getenv("HEVY_API_KEY")
 
        # Redis
        self.redis_url = os.getenv("REDIS_URL")
        self._redis = None
 
    async def _get_redis(self):
        if self._redis is None and self.redis_url:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                logger.info("Redis connected")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
        return self._redis
 
    async def _get_stored_whoop_token(self) -> Optional[str]:
        r = await self._get_redis()
        if r:
            try:
                token = await r.get("whoop_refresh_token")
                if token:
                    logger.info("Loaded Whoop refresh token from Redis")
                    return token
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        return self.whoop_refresh_token
 
    async def _save_whoop_token(self, token: str):
        self.whoop_refresh_token = token
        r = await self._get_redis()
        if r:
            try:
                await r.set("whoop_refresh_token", token)
                logger.info("Whoop refresh token saved to Redis")
            except Exception as e:
                logger.error(f"Redis save error: {e}")
 
    def clear_cache(self):
        self._cache = {}
        self._cache_time = {}
 
    def _is_cached(self, key: str) -> bool:
        if key not in self._cache:
            return False
        return time.time() - self._cache_time.get(key, 0) < CACHE_DURATION
 
    def _set_cache(self, key: str, data):
        self._cache[key] = data
        self._cache_time[key] = time.time()
 
    async def get_all_data(self) -> dict:
        whoop_task = self._get_whoop_data()
        strava_task = self._get_strava_data()
        hevy_task = self._get_hevy_data()
 
        whoop, strava, hevy = await asyncio.gather(
            whoop_task, strava_task, hevy_task,
            return_exceptions=True
        )
 
        return {
            "fetched_at": datetime.now().isoformat(),
            "whoop": whoop if not isinstance(whoop, Exception) else {"error": str(whoop)},
            "strava": strava if not isinstance(strava, Exception) else {"error": str(strava)},
            "hevy": hevy if not isinstance(hevy, Exception) else {"error": str(hevy)},
        }
 
    # ─────────────────────────────────────────────
    # WHOOP
    # ─────────────────────────────────────────────
 
    async def _get_whoop_access_token(self) -> Optional[str]:
        # Always fetch fresh - don't cache access token
        # Load latest refresh token from Redis
        refresh_token = await self._get_stored_whoop_token()
 
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://api.prod.whoop.com/oauth/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.whoop_client_id,
                    "client_secret": self.whoop_client_secret,
                    "scope": "offline read:recovery read:cycles read:workout read:sleep read:profile read:body_measurement"
                }
            )
            data = await resp.json()
            logger.info(f"Whoop token response keys: {list(data.keys())}")
            if "error" in data:
                logger.error(f"Whoop token error: {data}")
                raise Exception(f"Whoop auth failed: {data.get('error_description', data.get('error'))}")
            self._whoop_access_token = data.get("access_token")
            if "refresh_token" in data:
                await self._save_whoop_token(data["refresh_token"])
            return self._whoop_access_token
 
    async def _get_whoop_data(self) -> dict:
        if self._is_cached("whoop"):
            return self._cache["whoop"]
 
        token = await self._get_whoop_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        base = "https://api.prod.whoop.com/developer/v2"
 
        async with aiohttp.ClientSession(headers=headers) as session:
            async def fetch(url):
                r = await session.get(url)
                text = await r.text()
                logger.info(f"Whoop fetch {url}: {text[:200]}")
                if "Authorization was not valid" in text or r.status == 401:
                    self._whoop_access_token = None
                    raise Exception("Whoop token expired")
                try:
                    return json.loads(text)
                except Exception:
                    logger.error(f"Whoop fetch error for {url}: {text}")
                    return {}
 
            recovery, cycles, workouts, sleep = await asyncio.gather(
                fetch(f"{base}/recovery?limit=7"),
                fetch(f"{base}/cycle?limit=7"),
                fetch(f"{base}/activity/workout?limit=7"),
                fetch(f"{base}/activity/sleep?limit=7"),
            )
 
        result = {
            "recovery_records": recovery.get("records", []),
            "cycle_records": cycles.get("records", []),
            "workout_records": workouts.get("records", []),
            "sleep_records": sleep.get("records", []),
        }
 
        if result["recovery_records"]:
            latest = result["recovery_records"][0]
            score = latest.get("score", {})
            result["today"] = {
                "recovery_score": score.get("recovery_score"),
                "hrv_rmssd_milli": score.get("hrv_rmssd_milli"),
                "resting_heart_rate": score.get("resting_heart_rate"),
                "sleep_performance_percentage": score.get("sleep_performance_percentage"),
            }
 
        self._set_cache("whoop", result)
        return result
 
    # ─────────────────────────────────────────────
    # STRAVA
    # ─────────────────────────────────────────────
 
    async def _get_strava_access_token(self) -> Optional[str]:
        if self._strava_access_token:
            return self._strava_access_token
 
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.strava_client_id,
                    "client_secret": self.strava_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.strava_refresh_token,
                }
            )
            data = await resp.json()
            self._strava_access_token = data.get("access_token")
            return self._strava_access_token
 
    async def _get_strava_data(self) -> dict:
        if self._is_cached("strava"):
            return self._cache["strava"]
 
        token = await self._get_strava_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        base = "https://www.strava.com/api/v3"
 
        async with aiohttp.ClientSession(headers=headers) as session:
            after = int((datetime.utcnow() - timedelta(days=30)).timestamp())
 
            async def fetch(url):
                r = await session.get(url)
                return await r.json()
 
            activities, athlete = await asyncio.gather(
                fetch(f"{base}/athlete/activities?after={after}&per_page=50"),
                fetch(f"{base}/athlete"),
            )
 
        runs = [
            {
                "name": a.get("name"),
                "date": a.get("start_date_local", "")[:10],
                "distance_km": round(a.get("distance", 0) / 1000, 2),
                "duration_min": round(a.get("moving_time", 0) / 60, 1),
                "pace_min_per_km": round((a.get("moving_time", 0) / 60) / (a.get("distance", 1) / 1000), 2) if a.get("distance") else None,
                "elevation_gain_m": a.get("total_elevation_gain"),
                "average_heartrate": a.get("average_heartrate"),
                "max_heartrate": a.get("max_heartrate"),
                "suffer_score": a.get("suffer_score"),
                "type": a.get("type"),
            }
            for a in (activities if isinstance(activities, list) else [])
        ]
 
        result = {
            "athlete_name": athlete.get("firstname", "") if isinstance(athlete, dict) else "",
            "recent_activities": runs,
            "run_count_30d": sum(1 for r in runs if r["type"] == "Run"),
            "total_distance_km_30d": round(sum(r["distance_km"] for r in runs if r["type"] == "Run"), 1),
        }
 
        self._set_cache("strava", result)
        return result
 
    # ─────────────────────────────────────────────
    # HEVY
    # ─────────────────────────────────────────────
 
    async def _get_hevy_data(self) -> dict:
        if self._is_cached("hevy"):
            return self._cache["hevy"]
 
        if not self.hevy_api_key:
            return {"error": "No Hevy API key configured"}
 
        headers = {
            "api-key": self.hevy_api_key,
            "Content-Type": "application/json"
        }
        base = "https://api.hevyapp.com/v1"
 
        async with aiohttp.ClientSession(headers=headers) as session:
            r = await session.get(f"{base}/workouts?page=1&pageSize=20")
            text = await r.text()
            logger.info(f"Hevy response: {text[:200]}")
            try:
                data = json.loads(text)
            except Exception:
                return {"error": f"Hevy returned invalid response: {text[:100]}"}
 
        workouts = data.get("workouts", [])
 
        simplified = []
        for w in workouts:
            exercises = []
            for ex in w.get("exercises", []):
                sets = [
                    {
                        "reps": s.get("reps"),
                        "weight_kg": s.get("weight_kg"),
                    }
                    for s in ex.get("sets", [])
                    if s.get("type") == "normal"
                ]
                exercises.append({
                    "name": ex.get("title"),
                    "sets": sets,
                    "top_set_weight_kg": max((s["weight_kg"] for s in sets if s["weight_kg"]), default=None),
                })
 
            simplified.append({
                "date": w.get("start_time", "")[:10],
                "title": w.get("title"),
                "duration_min": round(w.get("duration", 0) / 60, 1),
                "exercise_count": len(exercises),
                "exercises": exercises,
            })
 
        result = {
            "recent_workouts": simplified,
            "workout_count": len(simplified),
        }
 
        self._set_cache("hevy", result)
        return result
