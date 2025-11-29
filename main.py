import time
import requests
import os
import sys
import threading
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

# --- CONFIGURATION ---
sys.stdout.reconfigure(line_buffering=True)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
COOKIE_STRING = os.environ.get("COOKIE_STRING") 

GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"
BASE_DOMAIN = "https://flashsport.bet"

# --- FAKE SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"
def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- TELEGRAM ---
def send_telegram_msg(message):
    print(f"🔔 {message}", flush=True)
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": CHAT_ID, "text": message})
        except: pass

def send_telegram_photo(file_path, caption=""):
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            with open(file_path, "rb") as photo:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", 
                              data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": photo})
        except: pass

# --- MOBILE BROWSER SETUP ---
def setup_driver():
    print("   -> Launching Chrome (Mobile Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    
    # 1. MOBILE SIZE
    opts.add_argument("--window-size=375,812")
    
    # 2. MOBILE IDENTITY (Matches Android)
    opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")

    if os.environ.get("CHROME_BIN"): 
        opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    
    # Stealth settings adjusted for Mobile
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
        print("❌ Error: COOKIE_STRING is missing!", flush=True)
        return False
        
    try:
        # TRICK: Go to the domain but a 404 page first. 
        # This sets the domain context so we can add cookies, 
        # but prevents the site from running its "Login Check" logic immediately.
        driver.get(BASE_DOMAIN + "/favicon.ico") 
        time.sleep(1)
        
        # Parse Cookies
        pairs = COOKIE_STRING.split(';')
        for pair in pairs:
            if '=' in pair:
                parts = pair.strip().split('=', 1)
                name = parts[0]
                value = parts[1]
                
                # Add cookie without forcing a specific domain (let Selenium decide)
                driver.add_cookie({
                    'name': name,
                    'value': value,
                    'path': '/'
                })
        
        print("✅ Cookies added.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Cookie Error: {e}", flush=True)
        return False

# --- MONITORING ---
def monitor_game(driver):
    print("🔎 Going to Game Page...", flush=True)
    driver.get(GAME_URL)
    time.sleep(15) # Wait for load
    
    # Check if redirected to login
    if "Sign" in driver.title or "Login" in driver.title:
        print("❌ Still redirected to Login.", flush=True)
        driver.save_screenshot("fail.png")
        send_telegram_photo("fail.png", "Still failed. The cookie might be bound to your IP address.")
        return False

    print("✅ SUCCESS! Game Loaded.", flush=True)
    send_telegram_msg("✅ Bot Connected! Cookies worked.")
    
    driver.save_screenshot("success.png")
    send_telegram_photo("success.png", "I see the game! Monitoring now...")
    
    # Keep alive loop
    start_time = time.time()
    while time.time() - start_time < 1800:
        time.sleep(5)
        
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
