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

# --- BROWSER SETUP (DESKTOP MODE) ---
def setup_driver():
    print("   -> Launching Desktop Chrome...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    
    # CRITICAL: Use Desktop Size to separate Chat Widget from Login Button
    opts.add_argument("--window-size=1920,1080")
    
    # Desktop User Agent
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver

# --- THE NUCLEAR CLEANER ---
def nuke_overlays(driver):
    """Deletes Chat Widgets, Cookies, and Banners to clear the click path"""
    print("   -> ☢️ NUKING OVERLAYS...", flush=True)
    driver.execute_script("""
        // Remove Tawk.to and other chat widgets
        var iframes = document.querySelectorAll('iframe');
        iframes.forEach(f => f.remove());
        
        // Remove cookie banners
        var banners = document.querySelectorAll('div[class*="cookie"], div[class*="modal"], div[class*="popup"]');
        banners.forEach(b => b.remove());
        
        // Remove Z-Index blockers
        var blockers = document.querySelectorAll('div[style*="z-index: 999"]');
        blockers.forEach(b => b.remove());
    """)
    time.sleep(1)

# --- HARDWARE LEVEL TYPING ---
def smart_type(driver, element, text):
    """Uses ActionChains to simulate real hardware keyboard events"""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    element.click()
    element.clear()
    
    actions = ActionChains(driver)
    actions.click(element)
    for char in text:
        actions.send_keys(char)
        actions.pause(0.1)
    actions.perform()
    
    time.sleep(0.5)
    # Trigger events manually to be safe
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting DESKTOP Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 20)
        time.sleep(5)
        
        # 1. Clean the page
        nuke_overlays(driver)
        
        # 2. Find Inputs
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            print("❌ Input Error: Not enough boxes.", flush=True)
            return False
            
        phone_in = visible[0]
        pass_in = visible[1]
        
        # 3. Type Credentials
        print("   -> Typing Credentials...", flush=True)
        smart_type(driver, phone_in, LOGIN_PHONE)
        time.sleep(1)
        smart_type(driver, pass_in, LOGIN_PASSWORD)
        time.sleep(1)
        
        # 4. Clean page again (Chat widget might have respawned)
        nuke_overlays(driver)

        # 5. FIND BUTTON (Priority: Submit Type)
        print("   -> Targeting Button...", flush=True)
        btn = None
        try:
            # Look for submit type (Yellow button)
            btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            print("      (Found Submit Button)", flush=True)
        except:
            try:
                # Look for Text
                btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
                print("      (Found Text Button)", flush=True)
            except: pass
            
        # 6. CLICK
        if btn:
            # Force enable
            driver.execute_script("arguments[0].removeAttribute('disabled');", btn)
            try:
                # Try standard click first
                btn.click()
                print("      -> Standard Click used.", flush=True)
            except:
                # Fallback to JS click
                driver.execute_script("arguments[0].click();", btn)
                print("      -> JS Click used.", flush=True)
        else:
            print("   -> Button missing. Pressing Enter...", flush=True)
            pass_in.send_keys(Keys.RETURN)

        # 7. Verify
        print("   -> Waiting for redirect...", flush=True)
        time.sleep(15)
        
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed. Dumping HTML body...", flush=True)
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Invalid" in body:
                print("   -> ERROR: Invalid Username/Password", flush=True)
                send_telegram("❌ Login Failed: Invalid Credentials")
            else:
                print(f"   -> PAGE TEXT SAMPLE: {body[:100]}", flush=True)
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
