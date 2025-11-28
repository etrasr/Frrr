import time
import requests
import os
import threading
import sys
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
sys.stdout.reconfigure(line_buffering=True)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# 1. WE CHANGE THE URL TO THE HOME PAGE (Public access)
GAME_URL = "https://flashsport.bet/"

# --- SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"
def run_server():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# --- TELEGRAM ---
def send_telegram(message):
    print(f"🔔 {message}", flush=True)
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": CHAT_ID, "text": message})
        except: pass

# --- BROWSER SETUP ---
def setup_driver():
    print("   -> Launching Chrome...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080") # Desktop view to see more
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    return driver

# --- MONITOR ---
def find_and_monitor_game(driver):
    print("🔎 Searching Home Page for Keno...", flush=True)
    
    # 1. Look for iframes (Prevew windows)
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"   -> Found {len(frames)} frames. Checking content...", flush=True)
    
    target_class = None
    
    # Check main page first
    potential_80s = driver.find_elements(By.XPATH, "//*[text()='80']")
    if len(potential_80s) > 0:
        print("   -> Found '80' on main page. Checking...", flush=True)
        # (Logic to detect grid on main page could be added here)

    # Check frames
    for i, frame in enumerate(frames):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            
            # Look for the grid
            potential_80s = driver.find_elements(By.XPATH, "//*[text()='80']")
            for el in potential_80s:
                cls = el.get_attribute("class")
                if cls:
                    base = cls.split()[0]
                    siblings = driver.find_elements(By.CLASS_NAME, base)
                    if 70 <= len(siblings) <= 90:
                        target_class = base
                        print(f"✅ LOCKED ON FRAME #{i+1} with Class: {target_class}", flush=True)
                        break
            if target_class: break
        except: continue
            
    if not target_class:
        print("❌ Could not find Keno grid on Home Page.", flush=True)
        # Capture title to see where we are
        print(f"   -> Current Title: {driver.title}", flush=True)
        return False

    send_telegram(f"✅ Bot Active (No Login Mode)! Watching...")
    
    last_alert = []
    start_time = time.time()
    
    while time.time() - start_time < 1200:
        # Use the logic from your bot.py: Look for 'blink' or 'active' classes
        script = f"""
        var changed = [];
        var els = document.getElementsByClassName('{target_class}');
        for (var i=0; i<els.length; i++) {{
            // Check if class changed (Selenium logic)
            if (els[i].className.length > '{target_class}'.length + 2) {{
                changed.push(els[i].innerText);
            }}
            // Check for 'blink' or 'flash' (bot.py logic)
            if (els[i].className.includes('blink') || els[i].className.includes('flash')) {{
                changed.push(els[i].innerText);
            }}
        }}
        return changed;
        """
        try:
            active = driver.execute_script(script)
            if active:
                active = list(set(active)) # Remove duplicates
                active.sort()
                if active != last_alert:
                    clean = [n for n in active if n.strip().isdigit()]
                    if clean:
                        msg = f"⚡ FLASH: {', '.join(clean)}"
                        print(msg, flush=True)
                        send_telegram(msg)
                        last_alert = active
        except: return False 
        time.sleep(0.1)
    return True

# --- MAIN ---
def main():
    threading.Thread(target=run_server, daemon=True).start()
    print("🚀 Bot Process Started (No Login Mode).", flush=True)
    
    while True:
        driver = None
        try:
            driver = setup_driver()
            print(f"   -> Loading URL: {GAME_URL}", flush=True)
            driver.get(GAME_URL)
            time.sleep(10)
            
            # Note: We skipped perform_login() entirely
                
            success = find_and_monitor_game(driver)
            
            if not success:
                print("   -> Failed to find game on Home Page.", flush=True)
            
        except Exception as e:
            print(f"💥 Crash: {e}", flush=True)
        finally:
            if driver: driver.quit()
            print("🔄 Restarting...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
