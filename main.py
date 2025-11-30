import time
import requests
import os
import sys
import threading
import random
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

# --- BROWSER SETUP (DESKTOP MODE) ---
def setup_driver():
    print("   -> Launching Chrome (Desktop Windows Mode)...", flush=True)
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    
    # DESKTOP RESOLUTION (Crucial for Trust)
    opts.add_argument("--window-size=1920,1080")
    
    # REMOVE AUTOMATION FLAGS
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    
    # STEALTH SETTINGS FOR WINDOWS
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    driver.set_page_load_timeout(60)
    return driver

# --- HUMAN TYPING ---
def slow_type(driver, element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.1, 0.3)) # Human typing speed

# --- LOGIN LOGIC ---
def perform_login(driver):
    send_msg("🔑 Starting Login Process (Desktop Mode)...")
    
    try:
        # 1. Load Page
        driver.get("https://flashsport.bet/en/auth/signin")
        
        # 2. THE TOKEN REFRESH TRICK
        # We wait 5 seconds, then REFRESH. This gives us a fresh ReCaptcha token.
        send_msg("⏳ Warming up ReCaptcha (5s)...")
        time.sleep(5)
        print("   -> Refreshing page to generate valid token...", flush=True)
        driver.refresh()
        time.sleep(8) # Wait for page + ReCaptcha to load fully
        
        debug_shot(driver, "1_desktop_login.png")
        
        # 3. Find Inputs
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            send_msg("❌ Inputs not found!")
            return False
            
        phone_box = visible[0]
        pass_box = visible[1]
        
        # 4. Type Credentials
        print("   -> Typing Phone...", flush=True)
        phone_box.click()
        phone_box.clear()
        slow_type(driver, phone_box, LOGIN_PHONE)
        time.sleep(1)
        
        print("   -> Typing Password...", flush=True)
        pass_box.click()
        pass_box.clear()
        slow_type(driver, pass_box, LOGIN_PASSWORD)
        time.sleep(2)
        
        # 5. MOUSE MOVEMENT + CLICK
        # We need to simulate mouse movement to prove we aren't a robot
        print("   -> Moving mouse to button...", flush=True)
        
        # Find button (Desktop layout might be slightly different, looking for text)
        xpath = "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log')]"
        try:
            login_btn = driver.find_element(By.XPATH, xpath)
        except:
            login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")

        # Move mouse over the button, wait, then click
        actions = ActionChains(driver)
        actions.move_to_element(login_btn)
        actions.pause(1)
        actions.click()
        actions.perform()
        
        print("   -> Clicked Login.", flush=True)
            
        # 6. Wait for Result
        send_msg("⏳ Waiting 15s for redirection...")
        time.sleep(15)
        debug_shot(driver, "2_result.png")
        
        # Check for error text
        body = driver.find_element(By.TAG_NAME, "body").text
        if "TOKEN error" in body:
            send_msg("❌ ReCaptcha still failed. Render IP is likely blacklisted.")
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
    while time.time() - start_time < 1800: # Restart every 30 mins
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
