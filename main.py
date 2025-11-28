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

# --- FORCE LOGS ---
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
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

# --- BROWSER ---
def setup_driver():
    print("   -> Launching Chrome...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90) # Increased timeout for slow connection
    return driver

# --- JS HELPER ---
def js_type(driver, element, value):
    driver.execute_script("""
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
    """, element, value)

# --- SMART LOGIN ---
def perform_universal_login(driver):
    print("🔑 Detect Login Page. Starting Universal Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 30) # Wait up to 30 seconds
        
        # 1. Find ALL Input fields
        print("   -> Searching for input boxes...", flush=True)
        # We wait for at least one input to appear
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        
        # Filter for visible inputs only
        visible_inputs = [i for i in inputs if i.is_displayed() and i.get_attribute('type') != 'hidden']
        print(f"   -> Found {len(visible_inputs)} visible inputs.", flush=True)
        
        if len(visible_inputs) < 2:
            print("❌ Not enough input fields found!", flush=True)
            # Dump page text to debug
            print(f"DEBUG PAGE TEXT: {driver.find_element(By.TAG_NAME, 'body').text[:200]}", flush=True)
            return False

        # 2. Strategy: 1st Input = Phone, Last Input (Password type) = Password
        phone_box = visible_inputs[0]
        
        # Find password box (look for type='password')
        pass_box = None
        for i in visible_inputs:
            if i.get_attribute('type') == 'password':
                pass_box = i
                break
        
        # If no password type found, just take the second box
        if not pass_box and len(visible_inputs) >= 2:
            pass_box = visible_inputs[1]
            
        # 3. Type Credentials
        print("   -> Injecting Phone...", flush=True)
        js_type(driver, phone_box, LOGIN_PHONE)
        time.sleep(1)
        
        print("   -> Injecting Password...", flush=True)
        js_type(driver, pass_box, LOGIN_PASSWORD)
        time.sleep(1)
        
        # 4. Click LOGIN Button
        print("   -> Clicking Login Button...", flush=True)
        # Search for any button with 'log' or 'sign' in text OR the 'yellow' button class if known
        # We try a broad XPath search
        clicked = False
        try:
            # Try text based
            btn = driver.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log')]")
            driver.execute_script("arguments[0].click();", btn)
            clicked = True
        except:
            # Try submit type
            try:
                btn = driver.find_element(By.XPATH, "//button[@type='submit']")
                driver.execute_script("arguments[0].click();", btn)
                clicked = True
            except:
                print("⚠️ Could not find specific Login button. Pressing ENTER on password box...", flush=True)
                pass_box.send_keys(u'\ue007') # Press Enter
                clicked = True

        time.sleep(15)
        
        # 5. Verify
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed. Still on login page.", flush=True)
            # Check for error text
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Invalid" in body or "Incorrect" in body:
                send_telegram("❌ Login Failed: Invalid Phone/Password.")
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
    
    # Keno Logic
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
    
    while time.time() - start_time < 1800:
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
                if not perform_universal_login(driver):
                    driver.quit()
                    time.sleep(30)
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
