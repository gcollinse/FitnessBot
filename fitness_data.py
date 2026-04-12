"""
Fitness Data Collector
Fetches data from Whoop, Hevy, and Strava APIs
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

RAILWAY_TOKEN = os.getenv("RAILWAY_TOKEN")
RAILWAY_SERVICE_ID = "b9bee61e-d784-4786-8b38-a1cf2166494e"
RAILWAY_ENVIRONMENT_ID = "ebbd9ac9-a0da-4871-9773-5c978c610e35"


async def update_railway_variable(name: str, value: str):
    """Update an environment variable in Railway"""
    if not RAILWAY_TOKEN:
        logger.warning("No RAILWAY_TOKEN set, cannot update variable")
        return
    try:
        query = """
        mutation variableUpsert($input: VariableUpsertInput!) {
            variableUpsert(input: $input)
        }
        """
        variables = {
            "input": {
                "serviceId": RAILWAY_SERVICE_ID,
                "environmentId": RAILWAY_ENVIRONMENT_ID,
                "name": name,
                "value": value
            }
        }
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://backboard.railway.com/graphql/v2",
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {RAILWAY_TOKEN}", "Content-Type": "application/json"}
            )
            result = await resp.json()
            if "errors" in result:
                logger.error(f"Railway variable update error: {result['errors']}")
            else:
                logger.info(f"Railway variable {name} updated successfully")
    except Exception as e:
        logger.error(f"Failed to update Railway variable: {e}")


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
        """Fetch all fitness data concurrently"""
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
        if self._whoop_access_token:
            return self._whoop_access_token

        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://api.prod.whoop.com/oauth/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.whoop_refresh_token,
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
                new_token = data["refresh_token"]
                self.whoop_refresh_token = new_token
                logger.info("Whoop refresh token rotated — saving to Railway")
                await update_railway_variable("WHOOP_REFRESH_TOKEN", new_token)
            return self._whoop_access_token

    async def _get_whoop_data(self) -> dict:
        if self._is_cached("whoop"):
            return self._cache["whoop"]

        token = await self._get_whoop_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        base = "https://api.prod.whoop.com/developer/v1"

        async with aiohttp.ClientSession(headers=headers) as session:
            end = datetime.utcnow()
            start = end - timedelta(days=7)
            start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")

            async def fetch(url):
                r = await session.get(url)
                return await r.json()

        recovery, cycles, workouts, sleep = await asyncio.gather(
            fetch(f"{base}/recovery?limit=7"),
            fetch(f"{base}/cycle?limit=7"),
            fetch(f"{base}/workout?limit=7"),
            fetch(f"{base}/sleep?limit=7"),
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
            data = await r.json()

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
