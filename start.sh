#!/bin/bash
# Build React frontend
npm install
npm run build

# Start FastAPI server
uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
