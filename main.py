import time
import requests
import os
import threading
import sys
import random
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

# --- STEALTH BROWSER SETUP ---
def setup_driver():
    print("   -> Launching Stealth Chrome...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=375,812") # iPhone X dimensions
    
    # HIDE SELENIUM TRACES
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    # MOBILE USER AGENT
    opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    
    # ADVANCED STEALTH: Overwrite the 'navigator.webdriver' property
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
    })
    
    driver.set_page_load_timeout(60)
    return driver

# --- SLOW TYPING ---
def slow_type(driver, element, text):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    element.click()
    element.clear()
    
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.2)) # Random typing speed
        
    time.sleep(0.5)
    # The "Shake" to wake up ReCaptcha
    element.send_keys(Keys.SPACE)
    time.sleep(0.1)
    element.send_keys(Keys.BACKSPACE)

# --- LOGIN ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting STEALTH Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Inputs
        print("   -> Locating inputs...", flush=True)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            print("❌ Input Error.", flush=True)
            return False
            
        phone_in = visible[0]
        pass_in = visible[1]
        
        # 2. Type Credentials
        print("   -> Typing Credentials...", flush=True)
        slow_type(driver, phone_in, LOGIN_PHONE)
        time.sleep(1)
        slow_type(driver, pass_in, LOGIN_PASSWORD)
        time.sleep(1)
        
        # 3. Find Button (Aggressive Search)
        print("   -> Clicking Login...", flush=True)
        btn_clicked = False
        
        # Strategy A: Text
        if not btn_clicked:
            try:
                btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
                driver.execute_script("arguments[0].click();", btn)
                btn_clicked = True
            except: pass
            
        # Strategy B: Submit Type
        if not btn_clicked:
            try:
                btn = driver.find_element(By.XPATH, "//button[@type='submit']")
                driver.execute_script("arguments[0].click();", btn)
                btn_clicked = True
            except: pass
            
        # Strategy C: Enter Key
        if not btn_clicked:
            print("   -> Using Enter Key fallback...", flush=True)
            pass_in.send_keys(Keys.RETURN)

        # 4. Wait & Check for ReCaptcha Error
        print("   -> Waiting for response...", flush=True)
        time.sleep(10)
        
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # CHECK FOR RECAPTCHA ERROR
        if "ReCaptcha" in body_text or "TOKEN error" in body_text:
            print("⚠️ ReCaptcha Blocked us. Refreshing to get a new token...", flush=True)
            return "RETRY"
            
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed. Still on page.", flush=True)
            if "Invalid" in body_text:
                send_telegram("❌ Login Failed: Invalid Credentials.")
                return False
            return "RETRY" # Try again if unknown error
            
        print("✅ Login Successful!", flush=True)
        return True

    except Exception as e:
        print(f"❌ Login Crash: {e}", flush=True)
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
    
    while time.time() - start_time < 1200: # 20 mins
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
            
            # LOGIN LOOP (Try 3 times)
            if "Sign" in driver.title or "auth" in driver.current_url:
                login_success = False
                for attempt in range(3):
                    print(f"🔄 Login Attempt {attempt+1}/3...", flush=True)
                    result = perform_login(driver)
                    
                    if result == True:
                        login_success = True
                        break
                    elif result == "RETRY":
                        print("   -> Retrying login in 5 seconds...", flush=True)
                        driver.refresh()
                        time.sleep(5)
                    else:
                        break # Stop on fatal error
                
                if not login_success:
                    print("❌ All login attempts failed.", flush=True)
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
