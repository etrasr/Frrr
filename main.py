import time
import requests
import os
import threading
import sys
import random
import json
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
sys.stdout.reconfigure(line_buffering=True)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LOGIN_PHONE = os.environ.get("LOGIN_PHONE")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD")
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

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
    print("   -> Launching Ultimate Chrome...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=375,812") # Mobile View
    opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")
    
    # Enable Logging to catch hidden errors
    d = DesiredCapabilities.CHROME
    d['goog:loggingPrefs'] = { 'browser':'ALL' }
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts, desired_capabilities=d)
    driver.set_page_load_timeout(60)
    return driver

# --- HELPER: DUMP ERROR LOGS ---
def dump_console_logs(driver):
    print("   -> 🛑 DUMPING BROWSER LOGS (Why did it fail?):", flush=True)
    try:
        logs = driver.get_log('browser')
        for log in logs:
            if log['level'] == 'SEVERE':
                print(f"      ❌ JS ERROR: {log['message']}", flush=True)
            elif "403" in str(log) or "401" in str(log):
                print(f"      ⛔ NETWORK BLOCK: {log['message']}", flush=True)
    except:
        print("      (Could not read logs)", flush=True)

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting ULTIMATE Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Clear Overlays (Cookies/Banners)
        try:
            cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'OK') or contains(text(), 'Allow')]")
            driver.execute_script("arguments[0].click();", cookie_btn)
            print("   -> Closed Cookie Banner.", flush=True)
            time.sleep(1)
        except: pass

        # 2. Inputs
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            print("❌ Input Error.", flush=True)
            return False
            
        phone_in = visible[0]
        pass_in = visible[1]
        
        # 3. Type Credentials
        print("   -> Typing Credentials...", flush=True)
        phone_in.clear()
        for char in LOGIN_PHONE:
            phone_in.send_keys(char)
            time.sleep(0.05)
        
        time.sleep(0.5)
        
        pass_in.clear()
        for char in LOGIN_PASSWORD:
            pass_in.send_keys(char)
            time.sleep(0.05)
            
        time.sleep(1)

        # 4. THE TRIPLE TAP STRATEGY
        print("   -> Executing Triple Tap Strategy...", flush=True)
        
        # A. Find the Submit Button (Priority 1)
        btn = None
        try:
            # Look for type="submit" (The yellow button usually has this)
            btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            print("      (Found 'Submit' Button)", flush=True)
        except:
            # Fallback to Text
            try:
                btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
                print("      (Found 'Text' Button)", flush=True)
            except: pass
            
        # B. Click Button
        if btn:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn)
                print("      -> Action 1: Clicked Button.", flush=True)
            except: pass
            
        # C. Press Enter (Backup)
        time.sleep(1)
        print("      -> Action 2: Pressing ENTER key...", flush=True)
        pass_in.send_keys(Keys.RETURN)
        
        # 5. Wait for Redirect
        print("   -> Waiting for result...", flush=True)
        time.sleep(15)
        
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed. Dumping info...", flush=True)
            
            # Check for onscreen errors
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Invalid" in body:
                print("   -> Site says: Invalid Username/Password", flush=True)
                send_telegram("❌ Login Failed: Invalid Credentials.")
            else:
                # If no text error, check internal logs
                dump_console_logs(driver)
            
            return False
            
        print("✅ Login Successful!", flush=True)
        return True

    except Exception as e:
        print(f"❌ Login Crash: {e}", flush=True)
        dump_console_logs(driver)
        return False

# --- MONITOR ---
def find_and_monitor_game(driver):
    print("🔎 Searching for Keno Grid...", flush=True)
    driver.switch_to.default_content()
    
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    target_class = None
    
    for i, frame in enumerate(frames):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
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
        print("❌ Could not find Keno grid.", flush=True)
        return False

    send_telegram(f"✅ Bot Active! Watching for flashes...")
    
    last_alert = []
    start_time = time.time()
    
    while time.time() - start_time < 1200:
        script = f"""
        var changed = [];
        var els = document.getElementsByClassName('{target_class}');
        for (var i=0; i<els.length; i++) {{
            if (els[i].className.length > '{target_class}'.length + 2) {{
                changed.push(els[i].innerText);
            }}
        }}
        return changed;
        """
        try:
            active = driver.execute_script(script)
            if active:
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
    print("🚀 Bot Process Started.", flush=True)
    
    while True:
        driver = None
        try:
            driver = setup_driver()
            print(f"   -> Loading URL...", flush=True)
            driver.get(GAME_URL)
            time.sleep(10)
            
            if "Sign" in driver.title or "auth" in driver.current_url:
                login_success = False
                for attempt in range(3):
                    print(f"🔄 Login Attempt {attempt+1}/3...", flush=True)
                    if perform_login(driver):
                        login_success = True
                        break
                    else:
                        driver.refresh()
                        time.sleep(5)
                
                if not login_success:
                    print("❌ Max attempts reached.", flush=True)
                    driver.quit()
                    time.sleep(60)
                    continue
                    
                driver.get(GAME_URL)
                time.sleep(10)
                
            success = find_and_monitor_game(driver)
            
        except Exception as e:
            print(f"💥 Crash: {e}", flush=True)
        finally:
            if driver: driver.quit()
            print("🔄 Restarting...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
