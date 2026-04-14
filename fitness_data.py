"""
Multi-user Fitness Data Collector
Fetches data using per-user tokens from the database
"""

import json
import time
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)
CACHE_DURATION = 30 * 60

_cache = {}
_cache_time = {}


class FitnessDataCollector:
    def __init__(self, user_id: str, tokens, save_whoop_token_fn: Optional[Callable] = None):
        self.user_id = user_id
        self.tokens = tokens
        self.save_whoop_token_fn = save_whoop_token_fn
        self._whoop_access_token = None
        self._strava_access_token = None

    def clear_cache(self):
        _cache.pop(self.user_id, None)
        _cache_time.pop(self.user_id, None)

    def _is_cached(self, key: str) -> bool:
        k = f"{self.user_id}:{key}"
        if k not in _cache:
            return False
        return time.time() - _cache_time.get(k, 0) < CACHE_DURATION

    def _set_cache(self, key: str, data):
        k = f"{self.user_id}:{key}"
        _cache[k] = data
        _cache_time[k] = time.time()

    def _get_cache(self, key: str):
        return _cache.get(f"{self.user_id}:{key}")

    async def get_all_data(self) -> dict:
        whoop_task = self._get_whoop_data()
        strava_task = self._get_strava_data()
        hevy_task = self._get_hevy_data()

        whoop, strava, hevy = await asyncio.gather(
            whoop_task, strava_task, hevy_task, return_exceptions=True
        )

        return {
            "fetched_at": datetime.now().isoformat(),
            "whoop": whoop if not isinstance(whoop, Exception) else {"error": str(whoop)},
            "strava": strava if not isinstance(strava, Exception) else {"error": str(strava)},
            "hevy": hevy if not isinstance(hevy, Exception) else {"error": str(hevy)},
        }

    async def _get_whoop_access_token(self) -> Optional[str]:
        if not self.tokens or not self.tokens.whoop_refresh_token:
            raise Exception("Whoop not connected")

        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://api.prod.whoop.com/oauth/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.tokens.whoop_refresh_token,
                    "client_id": self.tokens.whoop_client_id or __import__('os').getenv("WHOOP_CLIENT_ID"),
                    "client_secret": self.tokens.whoop_client_secret or __import__('os').getenv("WHOOP_CLIENT_SECRET"),
                    "scope": "offline read:recovery read:cycles read:workout read:sleep read:profile read:body_measurement"
                }
            )
            data = await resp.json()
            if "error" in data:
                raise Exception(f"Whoop auth failed: {data.get('error_description', data.get('error'))}")
            self._whoop_access_token = data.get("access_token")
            if "refresh_token" in data and self.save_whoop_token_fn:
                self.save_whoop_token_fn(self.user_id, data["refresh_token"])
                self.tokens.whoop_refresh_token = data["refresh_token"]
            return self._whoop_access_token

    async def _get_whoop_data(self) -> dict:
        if self._is_cached("whoop"):
            return self._get_cache("whoop")

        token = await self._get_whoop_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        base = "https://api.prod.whoop.com/developer/v2"

        async with aiohttp.ClientSession(headers=headers) as session:
            async def fetch(url):
                r = await session.get(url)
                text = await r.text()
                if "Authorization was not valid" in text or r.status == 401:
                    self._whoop_access_token = None
                    raise Exception("Whoop token expired")
                try:
                    return json.loads(text)
                except Exception:
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

    async def _get_strava_access_token(self) -> Optional[str]:
        if not self.tokens or not self.tokens.strava_refresh_token:
            raise Exception("Strava not connected")

        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.tokens.strava_client_id or __import__('os').getenv("STRAVA_CLIENT_ID"),
                    "client_secret": self.tokens.strava_client_secret or __import__('os').getenv("STRAVA_CLIENT_SECRET"),
                    "grant_type": "refresh_token",
                    "refresh_token": self.tokens.strava_refresh_token,
                }
            )
            data = await resp.json()
            self._strava_access_token = data.get("access_token")
            return self._strava_access_token

    async def _get_strava_data(self) -> dict:
        if self._is_cached("strava"):
            return self._get_cache("strava")

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
                "distance_miles": round(a.get("distance", 0) / 1609.34, 2),
                "duration_min": round(a.get("moving_time", 0) / 60, 1),
                "pace_min_per_mile": round((a.get("moving_time", 0) / 60) / (a.get("distance", 1) / 1609.34), 2) if a.get("distance") else None,
                "elevation_gain_ft": round(a.get("total_elevation_gain", 0) * 3.281, 0),
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
            "total_distance_miles_30d": round(sum(r["distance_miles"] for r in runs if r["type"] == "Run"), 1),
        }

        self._set_cache("strava", result)
        return result

    async def _get_hevy_data(self) -> dict:
        if self._is_cached("hevy"):
            return self._get_cache("hevy")

        if not self.tokens or not self.tokens.hevy_api_key:
            return {"error": "Hevy not connected"}

        headers = {"api-key": self.tokens.hevy_api_key, "Content-Type": "application/json"}
        base = "https://api.hevyapp.com/v1"

        async with aiohttp.ClientSession(headers=headers) as session:
            r = await session.get(f"{base}/workouts?page=1&pageSize=10")
            text = await r.text()
            logger.info(f"Hevy API response for {self.user_id}: {text[:300]}")
            try:
                data = json.loads(text)
            except Exception:
                return {"error": f"Hevy invalid response"}

        workouts = data.get("workouts", [])
        simplified = []
        for w in workouts:
            exercises = []
            for ex in w.get("exercises", []):
                sets = [{"reps": s.get("reps"), "weight_lbs": round(s.get("weight_kg", 0) * 2.205, 1)} for s in ex.get("sets", []) if s.get("type") == "normal"]
                exercises.append({
                    "name": ex.get("title"),
                    "sets": sets,
                    "top_set_weight_lbs": round(max((s["weight_lbs"] for s in sets if s["weight_lbs"]), default=0), 1),
                })
            simplified.append({
                "date": w.get("start_time", "")[:10],
                "title": w.get("title"),
                "duration_min": round(w.get("duration", 0) / 60, 1),
                "exercise_count": len(exercises),
                "exercises": exercises,
            })

        result = {"recent_workouts": simplified, "workout_count": len(simplified)}
        self._set_cache("hevy", result)
        return result
