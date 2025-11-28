# 1. Use a lightweight Python base
FROM python:3.9-slim

# 2. Install tools needed to download Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Google Chrome (Stable)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# 4. Set Environment Variable for Chrome
ENV CHROME_BIN=/usr/bin/google-chrome

# 5. Set working directory
WORKDIR /app

# 6. Copy your project files
COPY requirements.txt .
COPY main.py .

# 7. Install Python libraries
RUN pip install --no-cache-dir -r requirements.txt

# 8. Start the bot
CMD ["python", "main.py"]
