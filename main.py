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

# --- BROWSER SETUP (MOBILE) ---
def setup_driver():
    print("   -> Launching Chrome (Mobile Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    # 1. MOBILE EMULATION (Nexus 5X)
    mobile_emulation = { "deviceName": "Nexus 5X" }
    opts.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # 2. STEALTH FLAGS
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver

# --- HELPER: ROBUST TYPE (REACT COMPATIBLE) ---
def robust_type(driver, element, text):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    try: element.click(); element.clear()
    except: pass
    
    for char in text:
        element.send_keys(char)
        time.sleep(0.05)
    
    # FORCE REACT VALUE UPDATE
    driver.execute_script("""
        let input = arguments[0];
        let lastValue = input.value;
        input.value = arguments[1];
        let event = new Event('input', { bubbles: true });
        let tracker = input._valueTracker;
        if (tracker) { tracker.setValue(lastValue); }
        input.dispatchEvent(event);
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('blur', { bubbles: true }));
    """, element, text)
    time.sleep(0.5)

# --- LOGIN ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting GOD MODE Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Find Inputs
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
        robust_type(driver, phone_in, LOGIN_PHONE)
        robust_type(driver, pass_in, LOGIN_PASSWORD)
        
        # 3. GOD MODE BUTTON FINDER
        print("   -> Scanning DOM for ANY clickable 'LOGIN' element...", flush=True)
        
        # This script finds ANY element with text "LOGIN" below the password box
        # and triggers a Touch Event (Tap) instead of just a click.
        log = driver.execute_script("""
            var passBox = arguments[0];
            var passRect = passBox.getBoundingClientRect();
            var limitY = passRect.bottom;
            
            // Search every tag type
            var allElements = document.querySelectorAll('*');
            var target = null;
            
            for (var i = 0; i < allElements.length; i++) {
                var el = allElements[i];
                var rect = el.getBoundingClientRect();
                
                // Must be visible and below password
                if (rect.width === 0 || rect.height === 0 || rect.top <= limitY) continue;
                
                var txt = (el.innerText || el.textContent || "").trim().toUpperCase();
                
                // STRICT TEXT MATCH
                if (txt === "LOGIN" || txt === "LOG IN" || txt === "SIGN IN") {
                    
                    // Filter out header by checking parents
                    if (el.className.includes("header")) continue;
                    
                    target = el;
                    break;
                }
            }
            
            if (target) {
                target.scrollIntoView({block: 'center'});
                
                // DISPATCH TOUCH EVENTS (Mobile Tap)
                var touchObj = new Touch({
                    identifier: Date.now(),
                    target: target,
                    clientX: target.getBoundingClientRect().x,
                    clientY: target.getBoundingClientRect().y,
                    radiusX: 2.5,
                    radiusY: 2.5,
                    rotationAngle: 10,
                    force: 0.5,
                });
                
                var touchStart = new TouchEvent("touchstart", {
                    cancelable: true,
                    bubbles: true,
                    touches: [touchObj],
                    targetTouches: [],
                    changedTouches: [touchObj],
                    shiftKey: true,
                });
                
                var touchEnd = new TouchEvent("touchend", {
                    cancelable: true,
                    bubbles: true,
                    touches: [touchObj],
                    targetTouches: [],
                    changedTouches: [touchObj],
                    shiftKey: true,
                });
                
                target.dispatchEvent(touchStart);
                target.dispatchEvent(touchEnd);
                target.click(); // Backup click
                
                return "TAPPED: " + target.tagName + "." + target.className;
            }
            
            // DEBUG: If not found, dump nearby HTML
            return "NOT_FOUND";
        """, pass_in)
        
        print(f"   -> Result: {log}", flush=True)
        
        if log == "NOT_FOUND":
            print("⚠️ Button not found via JS. Dumping Form HTML for analysis:", flush=True)
            # Find the parent form or container of the password box
            try:
                parent = pass_in.find_element(By.XPATH, "./.. | ./../..")
                print(f"DEBUG HTML: {parent.get_attribute('outerHTML')[:500]}", flush=True)
            except: pass
            
            # Last resort enter key
            pass_in.send_keys(Keys.ENTER)

        # 4. Wait for Redirect
        print("   -> Waiting for redirect...", flush=True)
        time.sleep(15)
        
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed.", flush=True)
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
