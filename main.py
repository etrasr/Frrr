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

# --- FORCE LOGS ---
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LOGIN_PHONE = os.environ.get("LOGIN_PHONE")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD")
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

# --- SERVER (Keep Render Alive) ---
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
    # Matches your mobile screenshot user agent
    opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.105 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90)
    return driver

# --- HUMAN TYPING ---
def human_type(driver, element, text):
    """Clicks element and types text like a human to trigger site validation"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        element.click()
        element.clear()
        time.sleep(0.2)
        element.send_keys(text)
        time.sleep(0.5)
        # Trigger blur to ensure validation happens
        driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", element)
        return True
    except Exception as e:
        print(f"⚠️ Typing error: {e}", flush=True)
        return False

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting Human Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Identify Inputs by Placeholder/Type (More accurate)
        print("   -> Finding inputs...", flush=True)
        
        # Phone Input (Looking for 'Phone' in placeholder)
        phone_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Phone') or contains(@placeholder, 'username')]")))
        
        # Password Input
        pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
        
        # 2. Type Credentials
        print("   -> Typing Phone...", flush=True)
        human_type(driver, phone_input, LOGIN_PHONE)
        
        print("   -> Typing Password...", flush=True)
        human_type(driver, pass_input, LOGIN_PASSWORD)
        
        # 3. Click The BIG LOGIN Button
        print("   -> Clicking Login Button...", flush=True)
        
        # We look for the button specifically inside the form area, not the header
        # The XPath below looks for a button with text 'LOGIN' that comes AFTER the password field
        try:
            # Try pressing ENTER on the password field first (Most reliable)
            pass_input.send_keys(Keys.RETURN)
            print("      (Pressed ENTER key)", flush=True)
        except:
            # Fallback to clicking the submit button
            submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            driver.execute_script("arguments[0].click();", submit_btn)
            print("      (Clicked Submit button)", flush=True)
            
        time.sleep(15)
        
        # 4. Verify
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed. Still on login page.", flush=True)
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Invalid" in body or "Incorrect" in body:
                send_telegram("❌ Login Failed: Website says Invalid Phone/Password.")
            else:
                send_telegram("❌ Login Failed: Unknown reason (Button might be disabled).")
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
                if not perform_login(driver):
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
