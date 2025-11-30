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
from selenium_stealth import stealth
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
    print("   -> Launching Chrome...", flush=True)
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=375,812") # iPhone X Size
    
    # Hide Automation Flags
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    # Use User Agent directly
    opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"): opts.binary_location = os.environ.get("CHROME_BIN")
    
    driver = webdriver.Chrome(options=opts)
    
    # Activate Stealth
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Linux aarch64",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    driver.set_page_load_timeout(60)
    return driver

# --- SAFE INTERACTION (The Fix) ---
def safe_click(driver, element):
    """
    Clicks using JavaScript. Impossible to be 'out of bounds'.
    """
    try:
        # 1. Scroll into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        # 2. Click directly via JS engine
        driver.execute_script("arguments[0].click();", element)
    except Exception as e:
        print(f"   ⚠️ Safe Click failed: {e}")

def safe_type(driver, element, text):
    """
    Clears and types text safely.
    """
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    element.clear()
    time.sleep(0.2)
    element.send_keys(text)
    time.sleep(0.5)

# --- LOGIN LOGIC ---
def perform_login(driver):
    send_msg("🔑 Starting Safe Login...")
    
    try:
        driver.get("https://flashsport.bet/en/auth/signin")
        time.sleep(8)
        
        # 1. Find Inputs
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = driver.find_elements(By.TAG_NAME, "input")
        visible = [i for i in inputs if i.is_displayed()]
        
        if len(visible) < 2:
            send_msg("❌ Could not find inputs.")
            driver.save_screenshot("debug_no_input.png")
            send_photo("debug_no_input.png")
            return False
            
        phone_box = visible[0]
        pass_box = visible[1]
        
        # 2. Type Credentials
        print("   -> Typing Phone...", flush=True)
        safe_type(driver, phone_box, LOGIN_PHONE)
        
        print("   -> Typing Password...", flush=True)
        safe_type(driver, pass_box, LOGIN_PASSWORD)
        
        # 3. Find Button (Case Insensitive)
        print("   -> Hunting for Login Button...", flush=True)
        time.sleep(1)
        
        # Try finding button by text content
        login_btn = None
        try:
            login_btn = driver.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log')]")
        except:
            # Fallback to submit type
            try:
                login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            except:
                pass

        if login_btn:
            print("   -> Clicking Button via JS...", flush=True)
            safe_click(driver, login_btn)
        else:
            print("   -> Button not found. Using Enter Key...", flush=True)
            pass_box.send_keys(Keys.RETURN)
            
        # 4. Wait for Redirect
        send_msg("⏳ Waiting 15s for login...")
        time.sleep(15)
        
        if "auth" in driver.current_url:
            send_msg("❌ Login Failed. Still on login page.")
            driver.save_screenshot("login_fail.png")
            send_photo("login_fail.png", "Login Failed Screen")
            return False
            
        send_msg("✅ Login Successful!")
        return True

    except Exception as e:
        send_msg(f"❌ Login Error: {e}")
        return False

# --- MONITOR ---
def monitor_game(driver):
    send_msg("🔎 Loading Game Grid...")
    driver.get(GAME_URL)
    time.sleep(10)
    
    # Check if we got kicked back to login
    if "Sign" in driver.title:
        send_msg("❌ Redirected to Login. Retrying...")
        return False

    # Find the Keno Grid (1-80)
    target_class = None
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    
    # 1. Check iframes
    for frame in frames:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            if driver.find_elements(By.XPATH, "//*[text()='80']"):
                # Found the grid! Let's get the class name
                el = driver.find_element(By.XPATH, "//*[text()='80']")
                target_class = el.get_attribute("class").split()[0]
                print(f"✅ Found Grid in iframe! Class: {target_class}")
                break
        except: continue
        
    if not target_class:
        send_msg("❌ Could not find Keno Grid (Numbers 1-80).")
        driver.save_screenshot("no_grid.png")
        send_photo("no_grid.png")
        return False
        
    send_msg(f"✅ Bot Watching! Class: {target_class}")
    
    # 2. Watch Loop
    last_alert = []
    start_time = time.time()
    
    while time.time() - start_time < 1800: # 30 mins
        # JavaScript to find flashing elements
        script = f"""
        var changed = [];
        var els = document.getElementsByClassName('{target_class}');
        for (var i=0; i<els.length; i++) {{
            // If class name is longer than base, it has a modifier (active/green)
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
                        send_msg(msg)
                        last_alert = active
        except:
            return False
        time.sleep(0.1)
        
    return True

# --- MAIN ---
def main():
    threading.Thread(target=run_server, daemon=True).start()
    send_msg("🚀 Bot Restarted (Safe Mode).")
    
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
