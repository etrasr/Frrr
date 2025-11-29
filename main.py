import time
import requests
import os
import sys
import threading
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth

# --- CONFIGURATION ---
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
COOKIE_STRING = os.environ.get("COOKIE_STRING") 

GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"
BASE_URL = "https://flashsport.bet"

# --- FAKE SERVER (To keep Render alive) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"
def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- TELEGRAM FUNCTIONS ---
def send_telegram_msg(message):
    print(f"🔔 {message}", flush=True)
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        except Exception as e:
            print(f"Telegram Error: {e}")

def send_telegram_photo(file_path, caption=""):
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            with open(file_path, "rb") as photo:
                requests.post(url, data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": photo})
            print("📸 Screenshot sent to Telegram.")
        except Exception as e:
            print(f"Photo Error: {e}")

# --- BROWSER SETUP ---
def setup_driver():
    print("   -> Launching Chrome...", flush=True)
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    
    # Use desktop user agent to look normal
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    if os.environ.get("CHROME_BIN"): 
        opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    
    # Stealth Mode
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    driver.set_page_load_timeout(60)
    return driver

# --- COOKIE INJECTION ---
def inject_cookies(driver):
    print("🍪 Injecting Cookies...", flush=True)
    if not COOKIE_STRING:
        print("❌ Error: COOKIE_STRING is missing in Render Settings!", flush=True)
        return False
        
    try:
        # 1. Go to base domain
        driver.get(BASE_URL)
        time.sleep(3)
        
        # 2. Parse and add cookies
        # Cookies usually look like "name=value; name2=value2"
        pairs = COOKIE_STRING.split(';')
        for pair in pairs:
            if '=' in pair:
                parts = pair.strip().split('=', 1)
                name = parts[0]
                value = parts[1]
                
                driver.add_cookie({
                    'name': name,
                    'value': value,
                    'domain': 'flashsport.bet',
                    'path': '/'
                })
        
        print("✅ Cookies added.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Cookie Error: {e}", flush=True)
        return False

# --- MONITORING ---
def monitor_game(driver):
    print("🔎 Loading Game Page...", flush=True)
    driver.get(GAME_URL)
    time.sleep(15) # Wait for game to load
    
    # --- CHECK 1: LOGIN STATUS ---
    # If we see "Sign in" in title, cookies failed/expired
    if "Sign in" in driver.title or "Login" in driver.title:
        print("❌ Cookie Login Failed (Redirected to Login Page).", flush=True)
        send_telegram_msg("❌ Login Failed. Your Cookie String might be expired. Please get a new one.")
        
        # Take screenshot of error
        driver.save_screenshot("login_fail.png")
        send_telegram_photo("login_fail.png", "I am stuck here.")
        return False

    # --- CHECK 2: SUCCESS SNAPSHOT ---
    print("✅ Game Loaded! Sending verification screenshot...", flush=True)
    send_telegram_msg("✅ Bot Connected to Game! Sending screenshot now...")
    
    driver.save_screenshot("game_verify.png")
    send_telegram_photo("game_verify.png", "👀 Do you see the Keno grid here?")
    
    # --- LOOP ---
    print("👀 Watching game...", flush=True)
    start_time = time.time()
    
    # We refresh every 30 mins to keep session alive
    while time.time() - start_time < 1800:
        try:
            # Here we will add the "Flash Detection" later
            # For now, we just keep the connection alive to verify monitoring
            
            # Simple check to ensure page hasn't crashed
            driver.find_element(By.TAG_NAME, "body") 
            
            time.sleep(2)
        except Exception as e:
            print(f"Monitor loop warning: {e}", flush=True)
            break
            
    return True

# --- MAIN ---
def main():
    threading.Thread(target=run_server, daemon=True).start()
    print("🚀 Bot Process Started.", flush=True)
    
    while True:
        driver = None
        try:
            driver = setup_driver()
            
            if inject_cookies(driver):
                monitor_game(driver)
            
        except Exception as e:
            print(f"💥 Crash: {e}", flush=True)
        finally:
            if driver: driver.quit()
            print("🔄 Restarting...", flush=True)
            time.sleep(10)

if __name__ == "__main__":
    main()
