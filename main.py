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
from selenium.common.exceptions import TimeoutException

# --- FORCE LOGS TO APPEAR IMMEDIATELY ---
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LOGIN_PHONE = os.environ.get("LOGIN_PHONE")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD")
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

# --- FAKE WEB SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running..."

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- TELEGRAM ---
def send_telegram(message):
    print(f"🔔 {message}", flush=True)
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        except:
            pass

# --- BROWSER SETUP (LIGHTWEIGHT MODE) ---
def setup_driver():
    print("   -> Launching Chrome...", flush=True)
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # MEMORY SAVING OPTIONS
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1366,768") # Smaller window saves RAM
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=chrome_options)
    # Set a timeout so it doesn't freeze forever
    driver.set_page_load_timeout(60)
    return driver

# --- JS INJECTION ---
def force_input(driver, xpath, value):
    try:
        element = driver.find_element(By.XPATH, xpath)
        driver.execute_script("""
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, element, value)
        return True
    except Exception as e:
        print(f"⚠️ JS Injection failed: {e}", flush=True)
        return False

# --- LOGIN ---
def perform_deep_login(driver):
    print("🔑 Detect Login Page. Injecting credentials...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 15)
        
        # 1. Phone
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='tel' or contains(@name, 'phone')]")))
        force_input(driver, "//input[@type='tel' or contains(@name, 'phone')]", LOGIN_PHONE)
        time.sleep(1)
        
        # 2. Password
        force_input(driver, "//input[@type='password']", LOGIN_PASSWORD)
        time.sleep(1)
        
        # 3. Click
        print("   -> Clicking Login...", flush=True)
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
            driver.execute_script("arguments[0].click();", btn)
        except:
            btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            driver.execute_script("arguments[0].click();", btn)

        time.sleep(15)
        
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Stuck. Checking for errors...", flush=True)
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Invalid" in body or "Incorrect" in body:
                send_telegram("❌ Login Failed: Website says Invalid Credentials.")
            else:
                send_telegram(f"❌ Login Failed. Still on: {driver.title}")
            return False
            
        print("✅ Login Successful!", flush=True)
        return True

    except Exception as e:
        print(f"❌ Login Error: {e}", flush=True)
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
        except:
            continue
            
    if not target_class:
        print("❌ Could not find Keno grid.", flush=True)
        return False

    send_telegram(f"✅ Bot Active! Watching for flashes...")
    
    last_alert = []
    start_time = time.time()
    
    # Run for 20 mins then restart browser to free RAM
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
        except:
            return False 
        time.sleep(0.1)
        
    return True

# --- MAIN ---
def main():
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    print("🚀 Bot Process Started.", flush=True)
    
    while True:
        driver = None
        try:
            driver = setup_driver()
            print(f"   -> Loading URL: {GAME_URL}", flush=True)
            driver.get(GAME_URL)
            time.sleep(5)
            
            if "Sign" in driver.title or "auth" in driver.current_url:
                if not perform_deep_login(driver):
                    driver.quit()
                    time.sleep(30)
                    continue
                    
                driver.get(GAME_URL)
                time.sleep(10)
                
            success = find_and_monitor_game(driver)
            
        except TimeoutException:
            print("⚠️ Page load took too long (Timeout). Restarting...", flush=True)
        except Exception as e:
            print(f"💥 Crash: {e}", flush=True)
        finally:
            if driver:
                driver.quit()
            print("🔄 Browser restarting...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
