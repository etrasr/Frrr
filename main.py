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
sys.stdout.reconfigure(line_buffering=True) # Force logs to show instantly
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
    # Mobile User Agent
    opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver

# --- SLOW TYPING ENGINE ---
def slow_type(driver, element, text):
    """Types text one char at a time to trigger validation scripts"""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    element.click()
    element.clear()
    time.sleep(0.5)
    
    for char in text:
        element.send_keys(char)
        time.sleep(0.1) # Wait 0.1s between keys (Like a human)
    
    time.sleep(0.5)
    # The "Shake" maneuver: Type space then backspace to wake up the field
    element.send_keys(Keys.SPACE)
    time.sleep(0.1)
    element.send_keys(Keys.BACKSPACE)
    
    # Trigger events manually just in case
    driver.execute_script("""
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
    """, element)

# --- LOGIN LOGIC ---
def perform_login(driver):
    print("🔑 Detect Login Page. Starting SLOW LOGIN...", flush=True)
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Find Inputs
        print("   -> Locating inputs...", flush=True)
        # Look for the phone input (first input usually)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible_inputs = [i for i in inputs if i.is_displayed()]
        
        if len(visible_inputs) < 2:
            print("❌ Error: Could not find 2 visible inputs.", flush=True)
            return False
            
        phone_input = visible_inputs[0]
        # Try to find password specific input, otherwise take the second one
        pass_input = visible_inputs[1]
        for inp in visible_inputs:
            if inp.get_attribute("type") == "password":
                pass_input = inp
                break
        
        # 2. Type Credentials (SLOWLY)
        print(f"   -> Typing Phone ({LOGIN_PHONE})...", flush=True)
        slow_type(driver, phone_input, LOGIN_PHONE)
        
        print("   -> Typing Password...", flush=True)
        slow_type(driver, pass_input, LOGIN_PASSWORD)
        
        # 3. Handle Login Button
        print("   -> Hunting for Login Button...", flush=True)
        time.sleep(1)
        
        # Try to find the button
        login_btn = None
        try:
            # Look for button with text 'LOGIN'
            login_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
        except:
            try:
                # Look for submit button
                login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            except:
                print("⚠️ Could not find button element. Will try Enter key.", flush=True)

        # 4. FORCE ENABLE & CLICK
        if login_btn:
            # Debug: Print button status
            btn_html = login_btn.get_attribute('outerHTML')
            print(f"   -> Button found: {btn_html[:100]}...", flush=True)
            
            # HACK: Force remove 'disabled' attribute if it exists
            driver.execute_script("arguments[0].removeAttribute('disabled');", login_btn)
            driver.execute_script("arguments[0].classList.remove('disabled');", login_btn)
            time.sleep(0.5)
            
            print("   -> Clicking Button via JS...", flush=True)
            driver.execute_script("arguments[0].click();", login_btn)
        else:
            print("   -> Pressing ENTER on password field...", flush=True)
            pass_input.send_keys(Keys.RETURN)
            
        time.sleep(15)
        
        # 5. Verify
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Failed. Still on login page.", flush=True)
            
            # DEBUG: Print the page text to see the error
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "Invalid" in body_text:
                send_telegram("❌ Login Failed: Site says 'Invalid Username/Password'")
            else:
                # If no error text, maybe the button didn't work.
                print(f"DEBUG PAGE TEXT: {body_text[:200]}")
                send_telegram("❌ Login Failed: Unknown reason. Check logs.")
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
