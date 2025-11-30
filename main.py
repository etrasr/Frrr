import time
import requests
import os
import sys
import threading
import random
import math
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium_stealth import stealth

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
def send_msg(text):
    print(f"🔔 {text}", flush=True)
    if TELEGRAM_TOKEN and CHAT_ID:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": text})
        except: pass

def send_photo(filename, caption=""):
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            with open(filename, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": f})
        except: pass

# --- BROWSER SETUP (High Trust Desktop) ---
def setup_driver():
    print("   -> Launching Chrome (Physics Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=en-US")
    
    # CRITICAL: HIDE AUTOMATION
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    
    # STEALTH OVERLAY
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    return driver

# --- HUMAN PHYSICS ENGINE ---
def human_mouse_move(driver, element=None):
    """Moves mouse in a non-linear human curve"""
    action = ActionChains(driver)
    
    # If no target, move to random spot
    if element:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
        time.sleep(random.uniform(0.5, 1.0))
        action.move_to_element(element)
    else:
        # Jiggle in place
        action.move_by_offset(random.randint(-10, 10), random.randint(-10, 10))
    
    action.perform()
    time.sleep(random.uniform(0.2, 0.7))

def build_trust_score(driver):
    """Performs random actions to trick ReCaptcha v3"""
    send_msg("⏳ Building ReCaptcha Trust Score (20s)...")
    
    # 1. Random Scrolls
    for _ in range(3):
        driver.execute_script(f"window.scrollBy(0, {random.randint(100, 500)});")
        time.sleep(random.uniform(1, 3))
        human_mouse_move(driver) # Jiggle mouse
        driver.execute_script(f"window.scrollBy(0, {random.randint(-200, -50)});")
        time.sleep(random.uniform(1, 3))
    
    send_msg("   -> Trust building complete.")

def slow_type(driver, element, text):
    human_mouse_move(driver, element)
    element.click()
    time.sleep(0.5)
    element.clear()
    
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.1, 0.35)) # Variable typing speed
    
    time.sleep(0.5)

# --- LOGIN LOGIC ---
def perform_login(driver):
    send_msg("🔑 Starting Physics-Based Login...")
    
    try:
        # 1. Load Page & Build Trust
        driver.get("https://flashsport.bet/en/auth/signin")
        
        # DO NOT TYPE YET. WAIT AND ACT HUMAN.
        build_trust_score(driver)
        
        # 2. Find Inputs
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            send_msg("❌ Inputs not found!")
            return False
            
        phone_box = visible[0]
        pass_box = visible[1]
        
        # 3. Type Phone (Humanly)
        print("   -> Typing Phone...", flush=True)
        slow_type(driver, phone_box, LOGIN_PHONE)
        
        # 4. Type Password (Humanly)
        print("   -> Typing Password...", flush=True)
        slow_type(driver, pass_box, LOGIN_PASSWORD)
        
        # 5. Wait again for ReCaptcha to process the typing
        time.sleep(3)
        
        # 6. Find & Click Button
        print("   -> Targeting Login Button...", flush=True)
        
        # Locate the button that is AFTER the password box
        try:
            login_btn = driver.find_element(By.XPATH, "//input[@type='password']/following::button[contains(., 'LOGIN')]")
        except:
            login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")

        if login_btn:
            # Move mouse to button first
            human_mouse_move(driver, login_btn)
            time.sleep(0.5)
            
            # Click
            print("   -> CLICKING...", flush=True)
            login_btn.click()
        else:
            print("   -> Button missing, using Enter...", flush=True)
            pass_box.send_keys(Keys.RETURN)
            
        # 7. Wait for Result
        send_msg("⏳ Waiting 15s for result...")
        time.sleep(15)
        debug_shot(driver, "2_login_result.png")
        
        body = driver.find_element(By.TAG_NAME, "body").text
        if "TOKEN error" in body:
            send_msg("❌ ReCaptcha rejected us. Wait 2 mins and I will retry.")
            return False
        
        if "auth" in driver.current_url:
            send_msg("❌ Still on login page.")
            return False
            
        send_msg("✅ Login Successful!")
        return True

    except Exception as e:
        send_msg(f"❌ Error: {e}")
        return False

# --- MONITOR ---
def monitor_game(driver):
    send_msg("🔎 Loading Game...")
    driver.get(GAME_URL)
    time.sleep(15)
    debug_shot(driver, "3_game_loaded.png")
    
    if "Sign" in driver.title:
        send_msg("❌ Game redirected to Login.")
        return False

    send_msg("✅ Bot Connected! Watching now...")
    
    start_time = time.time()
    while time.time() - start_time < 1800:
        time.sleep(5)
    return True

# --- HELPER ---
def debug_shot(driver, name):
    driver.save_screenshot(name)
    send_photo(name, f"Debug: {name}")

# --- MAIN ---
def main():
    threading.Thread(target=run_server, daemon=True).start()
    send_msg("🚀 Bot Restarted.")
    
    while True:
        driver = None
        try:
            driver = setup_driver()
            
            if perform_login(driver):
                monitor_game(driver)
            
        except Exception as e:
            print(f"Crash: {e}")
        finally:
            if driver: driver.quit()
            print("Restarting...", flush=True)
            time.sleep(10)

if __name__ == "__main__":
    main()
