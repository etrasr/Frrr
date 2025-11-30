import time
import requests
import os
import sys
import threading
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

# --- BROWSER SETUP ---
def setup_driver():
    print("   -> Launching Chrome (Pixel 5 Emulation)...", flush=True)
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    
    # EMULATE PIXEL 5
    mobile_emulation = {
        "deviceMetrics": { "width": 393, "height": 851, "pixelRatio": 3.0 },
        "userAgent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36"
    }
    opts.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # STEALTH
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    
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

# --- HELPER: DEBUG SCREENSHOT ---
def debug_shot(driver, name):
    driver.save_screenshot(name)
    send_photo(name, f"Debug: {name}")

# --- LOGIN LOGIC ---
def perform_login(driver):
    send_msg("🔑 Starting Login Process...")
    
    try:
        # 1. Load Page
        driver.get("https://flashsport.bet/en/auth/signin")
        time.sleep(10)
        
        # 2. Find Inputs
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            send_msg("❌ Inputs not found!")
            debug_shot(driver, "error_no_inputs.png")
            return False
            
        phone_box = visible[0]
        pass_box = visible[1]
        
        # 3. Type Credentials
        print("   -> Typing Phone...", flush=True)
        phone_box.click()
        phone_box.clear()
        phone_box.send_keys(LOGIN_PHONE)
        time.sleep(1)
        
        print("   -> Typing Password...", flush=True)
        pass_box.click()
        pass_box.clear()
        pass_box.send_keys(LOGIN_PASSWORD)
        time.sleep(1)
        
        debug_shot(driver, "2_filled_form.png")
        
        # 4. FIND THE CORRECT BUTTON
        print("   -> Locating the BIG Yellow Button...", flush=True)
        
        # Strategy: Find the button that is physically located AFTER the password box
        # This prevents clicking the header button by mistake
        try:
            login_btn = driver.find_element(By.XPATH, "//input[@type='password']/following::button[contains(., 'LOGIN')]")
        except:
            # Fallback: Find the button with type='submit'
            try:
                login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            except:
                login_btn = None

        if login_btn:
            print("   -> Button Found! Force Clicking via JS...", flush=True)
            
            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_btn)
            time.sleep(1)
            
            # FORCE CLICK (JavaScript) - This works even if overlay/chat bubble is blocking it
            driver.execute_script("arguments[0].click();", login_btn)
        else:
            print("   -> Button NOT found. Using Enter Key fallback...", flush=True)
            pass_box.send_keys(Keys.RETURN)
            
        # 6. Wait for Result
        send_msg("⏳ Waiting 15s for redirection...")
        time.sleep(15)
        debug_shot(driver, "3_after_click.png")
        
        if "auth" in driver.current_url:
            send_msg("❌ Still on login page. Trying One More Click...")
            # Emergency Retry Click
            try:
                login_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
                driver.execute_script("arguments[0].click();", login_btn)
                time.sleep(10)
            except: pass
            
            if "auth" in driver.current_url:
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
    debug_shot(driver, "4_game_loaded.png")
    
    if "Sign" in driver.title:
        send_msg("❌ Game redirected to Login.")
        return False

    send_msg("✅ Bot Connected! Watching now...")
    
    start_time = time.time()
    while time.time() - start_time < 1800: # Restart every 30 mins
        time.sleep(5)
            
    return True

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
