FROM python:3.11-slim

# Install Chrome and dependencies - CORRECT PACKAGES
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
COPY keno_bot_final.py .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "keno_bot_final.py"]
