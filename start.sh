#!/bin/bash
# Start both the FastAPI server and the Telegram bot concurrently
uvicorn server:app --host 0.0.0.0 --port 8000 &
python bot_multi.py
