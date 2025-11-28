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

# --- MOBILE EMULATION ---
def setup_driver():
    print("   -> Launching Chrome (Pixel 5 Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    mobile_emulation = { "deviceName": "Pixel 5" }
    opts.add_experimental_option("mobileEmulation", mobile_emulation)
    
    opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(90) # Extended timeout for slow internet
    return driver

# --- HELPER: WAKE UP INPUT ---
def wake_up_input(driver, element):
    driver.execute_script("""
        let el = arguments[0];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
    """, element)

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting PATIENT Login...", flush=True)
    
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
        
        # 2. Type Credentials
        print("   -> Typing Credentials...", flush=True)
        phone_in.click(); phone_in.clear(); phone_in.send_keys(LOGIN_PHONE)
        time.sleep(0.5); wake_up_input(driver, phone_in)
        
        # Blur phone
        driver.find_element(By.TAG_NAME, "body").click()
        
        pass_in.click(); pass_in.clear(); pass_in.send_keys(LOGIN_PASSWORD)
        time.sleep(0.5); wake_up_input(driver, pass_in)
        
        # Blur password
        driver.find_element(By.TAG_NAME, "body").click()
        time.sleep(1)

        # 3. STRATEGY A: ENTER KEY (With 30s Monitor)
        print("   -> Attempting ENTER key submission...", flush=True)
        pass_in.send_keys(Keys.RETURN)
        
        print("   -> ⏳ Waiting up to 30 seconds for redirect...", flush=True)
        
        # We check every second for 30 seconds
        for i in range(30):
            if "auth" not in driver.current_url and "Sign" not in driver.title:
                print(f"      ✅ Success! Redirected after {i+1} seconds.", flush=True)
                print(f"      -> New Title: {driver.title}", flush=True)
                return True
            time.sleep(1)
            
        print("   -> ⚠️ Enter key timed out (30s). Trying Strategy B...", flush=True)

        # 4. STRATEGY B: CLICK BUTTON
        print("   -> Hunting for Login Button...", flush=True)
        
        # Find ANY button that looks right
        btn = None
        candidates = driver.find_elements(By.XPATH, "//button | //input[@type='submit']")
        for c in candidates:
            txt = c.text.strip().lower()
            if "login" in txt or "sign" in txt:
                btn = c
                break
                
        if btn:
            print(f"      -> Found button: {btn.text}", flush=True)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            try:
                btn.click()
            except:
                driver.execute_script("arguments[0].click();", btn)
            print("      -> Button Clicked.", flush=True)
            
            # Wait another 30s
            print("   -> ⏳ Waiting another 30s for redirect...", flush=True)
            for i in range(30):
                if "auth" not in driver.current_url and "Sign" not in driver.title:
                    print(f"      ✅ Success! Redirected after {i+1} seconds.", flush=True)
                    return True
                time.sleep(1)
        else:
            print("      -> No button found.", flush=True)

        # Final Failure Report
        print("❌ Login Failed. Dumping HTML info...", flush=True)
        body = driver.find_element(By.TAG_NAME, "body").text
        if "Invalid" in body:
            print("   -> Site says: Invalid Credentials", flush=True)
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
