FROM python:3.11-slim

# Install Chrome and dependencies
RUN apt-get update && apt-get install -y \
    chromium-browser \
    chromium-driver \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy files
COPY requirements.txt .
COPY keno_bot_final.py .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run bot
CMD ["python", "keno_bot_final.py"]
