import time
import requests
import os
import threading
import sys
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
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

# --- REAL MOBILE EMULATION ---
def setup_driver():
    print("   -> Launching Chrome (Pixel 5 Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    # Enable True Mobile Emulation
    mobile_emulation = { "deviceName": "Pixel 5" }
    opts.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # Logging
    opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting PIXEL 5 Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 20)
        time.sleep(3)
        
        # 1. Inputs
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            print("❌ Input Error.", flush=True)
            return False
            
        phone_in = visible[0]
        pass_in = visible[1]
        
        # 2. Type Credentials & BLUR
        print("   -> Typing Credentials...", flush=True)
        
        # Phone
        phone_in.click()
        phone_in.clear()
        phone_in.send_keys(LOGIN_PHONE)
        time.sleep(0.5)
        
        # Click the "Header" or Body to blur the phone input
        driver.find_element(By.TAG_NAME, "body").click()
        time.sleep(0.5)
        
        # Password
        pass_in.click()
        pass_in.clear()
        pass_in.send_keys(LOGIN_PASSWORD)
        time.sleep(0.5)
        
        # Click Body again to validate password
        driver.find_element(By.TAG_NAME, "body").click()
        time.sleep(1)

        # 3. SUBMIT STRATEGY
        print("   -> Attempting Submission...", flush=True)
        
        # Strategy A: Press ENTER on Password (Most reliable on mobile)
        print("      (Pressing ENTER)", flush=True)
        pass_in.send_keys(Keys.RETURN)
        
        # Wait small bit to see if it redirects
        time.sleep(5)
        
        # Strategy B: If still on login, Click the Button
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("      (Enter didn't work. Finding Button...)", flush=True)
            try:
                # Find the yellow button
                btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
                # Scroll it into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                # Click
                btn.click()
                print("      (Clicked 'LOGIN' Button)", flush=True)
            except:
                try:
                    btn = driver.find_element(By.XPATH, "//button[@type='submit']")
                    btn.click()
                    print("      (Clicked 'Submit' Button)", flush=True)
                except: pass

        # 4. Verify
        print("   -> Waiting for redirect...", flush=True)
        time.sleep(15)
        
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed. Dumping page text...", flush=True)
            body = driver.find_element(By.TAG_NAME, "body").text
            # Look for specific error messages
            if "Invalid" in body or "Incorrect" in body:
                print("   -> ERROR: Invalid Credentials", flush=True)
                send_telegram("❌ Login Failed: Invalid Credentials")
            elif "blocked" in body:
                print("   -> ERROR: Account Blocked", flush=True)
            else:
                print(f"   -> UNKNOWN ERROR. Page Text Sample: {body[:100]}")
            return False
            
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
