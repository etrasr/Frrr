import time
import requests
import os
import threading
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LOGIN_PHONE = os.environ.get("LOGIN_PHONE")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD")
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

# --- FAKE WEB SERVER (To keep Render happy) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running..."

def run_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- TELEGRAM FUNCTION ---
def send_telegram(message):
    print(f"🔔 {message}")
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        except:
            pass

# --- BROWSER SETUP ---
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Crucial: Look exactly like a real Android phone
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ.get("CHROME_BIN")
    
    return webdriver.Chrome(options=chrome_options)

# --- THE "MAGIC" JAVASCRIPT TYPING FUNCTION ---
def force_input(driver, xpath, value):
    """
    Finds an element and forces the value using JavaScript.
    This bypasses disabled buttons and event listeners.
    """
    try:
        element = driver.find_element(By.XPATH, xpath)
        # This script sets the value AND tells the website "The value just changed!"
        driver.execute_script("""
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, element, value)
        return True
    except Exception as e:
        print(f"⚠️ JS Injection failed for {value}: {e}")
        return False

# --- LOGIN LOGIC ---
def perform_deep_login(driver):
    print("🔑 Starting DEEP LOGIN process...")
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Inject Phone
        print("   - Injecting Phone...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='tel' or contains(@name, 'phone')]")))
        force_input(driver, "//input[@type='tel' or contains(@name, 'phone')]", LOGIN_PHONE)
        time.sleep(1)
        
        # 2. Inject Password
        print("   - Injecting Password...")
        force_input(driver, "//input[@type='password']", LOGIN_PASSWORD)
        time.sleep(1)
        
        # 3. Force Click Login
        print("   - Force Clicking Login...")
        try:
            # Try specific text first
            btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
            driver.execute_script("arguments[0].click();", btn)
        except:
            # Try generic submit button
            btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            driver.execute_script("arguments[0].click();", btn)

        # 4. Wait for redirection
        print("   - Waiting for redirect...")
        time.sleep(15)
        
        # 5. Check Result
        if "auth" in driver.current_url or "Sign" in driver.title:
            print("❌ Login Stuck. Dumping page text to find error...")
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Invalid" in body:
                send_telegram("❌ Login Failed: Website says Invalid Credentials.")
            else:
                send_telegram(f"❌ Login Failed. URL: {driver.current_url}")
            return False
            
        print("✅ Login Successful!")
        return True

    except Exception as e:
        print(f"❌ Login Crashed: {e}")
        return False

# --- GAME FINDING LOGIC ---
def find_and_monitor_game(driver):
    print("🔎 Searching for Keno Grid...")
    
    # Switch to default content to start fresh
    driver.switch_to.default_content()
    
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"  - Found {len(frames)} frames.")
    
    target_class = None
    
    # 1. Find the Grid
    for i, frame in enumerate(frames):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            
            # Look for '80'
            potential_80s = driver.find_elements(By.XPATH, "//*[text()='80']")
            for el in potential_80s:
                cls = el.get_attribute("class")
                if cls:
                    base = cls.split()[0]
                    siblings = driver.find_elements(By.CLASS_NAME, base)
                    if 70 <= len(siblings) <= 90:
                        target_class = base
                        print(f"✅ LOCKED ON FRAME #{i+1} with Class: {target_class}")
                        break
            if target_class: break
        except:
            continue
            
    if not target_class:
        print("❌ Could not find Keno grid in any frame.")
        return False

    send_telegram(f"✅ Bot Active! Watching for flashes...")
    
    # 2. Watch Loop
    last_alert = []
    
    # Run loop for 30 minutes then reload page to stay fresh
    start_time = time.time()
    
    while time.time() - start_time < 1800:
        script = f"""
        var changed = [];
        var els = document.getElementsByClassName('{target_class}');
        for (var i=0; i<els.length; i++) {{
            // If class name is longer than base, it has a modifier (green/active)
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
                    # Clean data
                    clean = [n for n in active if n.strip().isdigit()]
                    if clean:
                        msg = f"⚡ FLASH: {', '.join(clean)}"
                        print(msg)
                        send_telegram(msg)
                        last_alert = active
        except:
            print("⚠️ Lost frame connection.")
            return False # Break to restart logic
            
        time.sleep(0.1)
        
    return True # Time to reload

# --- MAIN EXECUTION ---
def main():
    # Start Dummy Server in Background
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    print("🚀 Bot Process Started.")
    
    while True:
        try:
            driver = setup_driver()
            driver.get(GAME_URL)
            time.sleep(5)
            
            if "Sign" in driver.title or "auth" in driver.current_url:
                if not perform_deep_login(driver):
                    driver.quit()
                    time.sleep(60) # Wait before retry
                    continue
                    
                # Force reload game after login
                driver.get(GAME_URL)
                time.sleep(10)
                
            # Start Monitoring
            success = find_and_monitor_game(driver)
            
            driver.quit()
            if not success:
                print("🔄 Restarting browser due to failure...")
                time.sleep(5)
            
        except Exception as e:
            print(f"💥 Main Crash: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
