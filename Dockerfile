FROM python:3.11-slim

# Install Node.js
RUN apt-get update && apt-get install -y \
    curl \
    libpq-dev \
    gcc \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy all files
COPY . .

# Build React frontend
RUN npm install && npm run build

# Start server
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port $PORT"]
