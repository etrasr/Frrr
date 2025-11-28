import time
import requests
import os
import threading
import sys
import json
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

# --- BROWSER SETUP (CDP ENABLED) ---
def setup_driver():
    print("   -> Launching Chrome (Pixel 5 + CDP Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=393,851") # Pixel 5
    
    # Manual Mobile Emulation (Prevents 'Invalid Device' crash)
    mobile_ua = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36"
    opts.add_argument(f"user-agent={mobile_ua}")
    opts.add_experimental_option("mobileEmulation", {
        "deviceMetrics": { "width": 393, "height": 851, "pixelRatio": 3.0, "touch": True },
        "userAgent": mobile_ua
    })
    
    opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90)
    return driver

# --- CDP HELPER FUNCTIONS (THE ENGINE FIX) ---
def cdp_click(driver, element):
    """Calculates screen coordinates and clicks using the browser engine."""
    try:
        # Get coordinates
        rect = driver.execute_script("return arguments[0].getBoundingClientRect();", element)
        x = rect['x'] + (rect['width'] / 2)
        y = rect['y'] + (rect['height'] / 2)
        
        # Simulate Touch Start
        driver.execute_cdp_cmd("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": x, "y": y}]
        })
        # Simulate Touch End (Click)
        driver.execute_cdp_cmd("Input.dispatchTouchEvent", {
            "type": "touchEnd",
            "touchPoints": []
        })
        print("      (CDP Touch Event Sent)", flush=True)
    except Exception as e:
        print(f"      (CDP Click failed: {e})", flush=True)

def cdp_type(driver, text):
    """Types text directly into the browser engine (Indistinguishable from human)."""
    for char in text:
        driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "keyDown", "text": char, "unmodifiedText": char, "windowsVirtualKeyCode": ord(char), "nativeVirtualKeyCode": ord(char)
        })
        driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "keyUp", "text": char, "unmodifiedText": char, "windowsVirtualKeyCode": ord(char), "nativeVirtualKeyCode": ord(char)
        })
        time.sleep(0.05) # Tiny delay between keys

def cdp_enter(driver):
    """Hits the Enter key at the hardware level."""
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
        "type": "keyDown", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13, "text": "\r", "unmodifiedText": "\r"
    })
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
        "type": "keyUp", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13, "text": "\r", "unmodifiedText": "\r"
    })

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting HARDWARE SIMULATION Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 30)
        time.sleep(5)
        
        # 1. Inputs
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            print("❌ Input Error.", flush=True)
            return False
            
        phone_in = visible[0]
        pass_in = visible[1]
        
        # 2. Type Credentials (CDP Mode)
        print("   -> Typing Phone (Hardware Level)...", flush=True)
        phone_in.click() # Focus
        time.sleep(0.5)
        cdp_type(driver, LOGIN_PHONE)
        
        time.sleep(1)
        
        print("   -> Typing Password (Hardware Level)...", flush=True)
        pass_in.click() # Focus
        time.sleep(0.5)
        cdp_type(driver, LOGIN_PASSWORD)
        
        time.sleep(1)

        # 3. ATTEMPT 1: HARDWARE ENTER
        print("   -> Hitting ENTER (Hardware Level)...", flush=True)
        cdp_enter(driver)
        
        # 4. WAIT 30 SECONDS
        print("   -> ⏳ Waiting 30s for redirect...", flush=True)
        for i in range(30):
            if "auth" not in driver.current_url and "Sign" not in driver.title:
                print(f"      ✅ Success! Redirected after {i+1} seconds.", flush=True)
                return True
            time.sleep(1)
            
        print("   -> ⚠️ Enter key timed out. Attempt 2: Button...", flush=True)
        
        # 5. ATTEMPT 2: HARDWARE TOUCH
        btn = None
        try:
            # Try finding the specific login button text
            btn = driver.find_element(By.XPATH, "//*[contains(translate(text(), 'LOGIN', 'login'), 'login')]")
        except:
            # Fallback to submit
            try: btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            except: pass
            
        if btn:
            print(f"      -> Found Button: {btn.text}", flush=True)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            
            # Use CDP Touch
            cdp_click(driver, btn)
            
            # Wait another 20s
            for i in range(20):
                if "auth" not in driver.current_url: return True
                time.sleep(1)
        
        # Final Failure
        print("❌ Login Failed. Dumping Info...", flush=True)
        body = driver.find_element(By.TAG_NAME, "body").text
        
        # Detect Errors
        if "Invalid" in body or "Incorrect" in body:
            send_telegram("❌ Login Failed: Website says Invalid Credentials")
        elif "blocked" in body.lower():
            send_telegram("❌ Login Failed: Account Blocked")
        else:
            print(f"   -> PAGE DUMP: {body[:200]}", flush=True)
            
        return False

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
                        print("   -> Restarting browser...", flush=True)
                        driver.quit()
                        driver = setup_driver()
                        driver.get(GAME_URL)
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
