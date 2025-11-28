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

# --- BROWSER SETUP (STABLE MOBILE MODE) ---
def setup_driver():
    print("   -> Launching Chrome (Manual Config)...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    # 1. Size
    opts.add_argument("--window-size=393,851") 
    
    # 2. User Agent
    mobile_ua = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36"
    opts.add_argument(f"user-agent={mobile_ua}")
    
    # 3. Emulation (Manual Dictionary to prevent crashes)
    opts.add_experimental_option("mobileEmulation", {
        "deviceMetrics": { "width": 393, "height": 851, "pixelRatio": 3.0, "touch": True },
        "userAgent": mobile_ua
    })
    
    opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90)
    return driver

# --- THE INPUT HACK (CRITICAL FIX) ---
def inject_value(driver, element, value):
    """
    Bypasses React/Angular validation by using the native browser setter.
    This forces the website to accept the input.
    """
    driver.execute_script("""
        let input = arguments[0];
        let text = arguments[1];
        
        // 1. Get the native setter from the browser prototype
        let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        
        // 2. Call it directly on the input (Bypassing React's listeners)
        nativeInputValueSetter.call(input, text);
        
        // 3. Dispatch events to wake up the submit button
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('blur', { bubbles: true }));
    """, element, value)

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting INJECTION Login...", flush=True)
    
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
        
        # 2. INJECT Credentials
        print("   -> Injecting Phone...", flush=True)
        inject_value(driver, phone_in, LOGIN_PHONE)
        time.sleep(1)
        
        print("   -> Injecting Password...", flush=True)
        inject_value(driver, pass_in, LOGIN_PASSWORD)
        time.sleep(1)

        # 3. Find Button (By Text)
        print("   -> Finding 'LOGIN' Button...", flush=True)
        btn = None
        try:
            # Look for explicit LOGIN text
            btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
        except:
            # Fallback to submit type
            try: btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            except: pass
            
        if btn:
            print(f"      -> Found: {btn.text}", flush=True)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            
            # CLICK
            print("      -> Clicking Button...", flush=True)
            driver.execute_script("arguments[0].click();", btn)
            
            # 4. WAIT 30 SECONDS (As requested)
            print("   -> ⏳ Waiting 30 seconds for login to finish...", flush=True)
            for i in range(30):
                if "auth" not in driver.current_url and "Sign" not in driver.title:
                    print(f"      ✅ Success! Redirected after {i+1} seconds.", flush=True)
                    return True
                time.sleep(1)
                
            print("   -> ⚠️ Button click timed out. Trying ENTER key...", flush=True)
        
        # 5. Backup: Enter Key
        pass_in.send_keys(Keys.RETURN)
        print("   -> Pressed ENTER. Waiting 30s...", flush=True)
        time.sleep(30)
        
        # Final Check
        if "auth" not in driver.current_url and "Sign" not in driver.title:
            print("      ✅ Success! Redirected.", flush=True)
            return True

        print("❌ Login Failed.", flush=True)
        body = driver.find_element(By.TAG_NAME, "body").text
        if "Invalid" in body:
            send_telegram("❌ Login Failed: Invalid Credentials")
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
