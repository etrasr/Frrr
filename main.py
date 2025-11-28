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

# --- BROWSER SETUP (STABLE MOBILE) ---
def setup_driver():
    print("   -> Launching Chrome (Pixel 5 Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=393,851") 
    
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

# --- THE INPUT HACK ---
def inject_value(driver, element, value):
    """Bypasses React validation"""
    driver.execute_script("""
        let input = arguments[0];
        let text = arguments[1];
        let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        setter.call(input, text);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('blur', { bubbles: true }));
    """, element, value)

# --- CLEANER ---
def nuke_overlays(driver):
    try:
        driver.execute_script("""
            document.querySelectorAll('iframe').forEach(e => e.remove());
            document.querySelectorAll('div[class*="cookie"]').forEach(e => e.remove());
            document.querySelectorAll('div[style*="z-index: 999"]').forEach(e => e.remove());
        """)
    except: pass

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting FINAL FIX Login...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 30)
        time.sleep(5)
        nuke_overlays(driver)
        
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
        print("   -> Injecting Credentials...", flush=True)
        inject_value(driver, phone_in, LOGIN_PHONE)
        time.sleep(0.5)
        inject_value(driver, pass_in, LOGIN_PASSWORD)
        
        # CRITICAL PAUSE: Let the site realize the box is full
        print("   -> Pausing 2s for UI update...", flush=True)
        time.sleep(2)

        # 3. FIND BUTTON
        print("   -> Hunting for LOGIN Button...", flush=True)
        btn = None
        
        # Try finding by TEXT
        try:
            # Looks for "LOGIN" in any element
            btn = driver.find_element(By.XPATH, "//*[contains(translate(text(), 'LOGIN', 'login'), 'login')]")
            if btn.tag_name not in ['button', 'div', 'a', 'span']: btn = None # Filter bad tags
        except: pass
        
        # Try finding by TYPE
        if not btn:
            try: btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            except: pass
            
        if btn:
            print(f"      -> Target Acquired: <{btn.tag_name}> '{btn.text}'", flush=True)
            
            # FORCE ENABLE (Remove disabled attribute)
            driver.execute_script("arguments[0].removeAttribute('disabled');", btn)
            driver.execute_script("arguments[0].classList.remove('disabled');", btn)
            
            # SCROLL
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(1)
            
            # ATTACK 1: ActionChain Click (Physical)
            print("      -> Click 1: Physical...", flush=True)
            try:
                actions = ActionChains(driver)
                actions.move_to_element(btn).click().perform()
            except: pass
            
            time.sleep(0.5)
            
            # ATTACK 2: JS Click (Direct)
            print("      -> Click 2: JavaScript...", flush=True)
            driver.execute_script("arguments[0].click();", btn)
            
        else:
            print("      -> ⚠️ No Button Found. Skipping to Form Submit.", flush=True)

        # ATTACK 3: FORM SUBMIT (The "Ghost" Submit)
        print("   -> Action 3: Force Form Submit...", flush=True)
        try:
            driver.execute_script("document.querySelector('form').submit();")
        except: 
            print("      (No form tag found)", flush=True)

        # 4. WAIT FOR REDIRECT
        print("   -> ⏳ Waiting 30 seconds for redirect...", flush=True)
        for i in range(30):
            if "auth" not in driver.current_url and "Sign" not in driver.title:
                print(f"      ✅ SUCCESS! Login Completed.", flush=True)
                return True
            time.sleep(1)

        # Final Check
        print("❌ Login Failed. Button clicks didn't trigger redirect.", flush=True)
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
