# 1. Use Python 3.9 Slim
FROM python:3.9-slim

# 2. Install tools needed to download files
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 3. Download and Install Google Chrome directly (No keys needed)
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get update && apt-get install -y ./google-chrome-stable_current_amd64.deb
RUN rm google-chrome-stable_current_amd64.deb

# 4. Tell the bot where Chrome is
ENV CHROME_BIN=/usr/bin/google-chrome

# 5. Setup Project
WORKDIR /app

# 6. Copy files
COPY requirements.txt .
COPY main.py .

# 7. Install Python libraries
RUN pip install --no-cache-dir -r requirements.txt

# 8. Start
CMD ["python", "main.py"]
