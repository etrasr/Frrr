import time
import requests
import os
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

# The specific game URL
GAME_URL = "https://flashsport.bet/en/casino?game=%2Fkeno1675&returnUrl=casino"

def send_telegram(message):
    print(f"🔔 {message}")
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": message})
        except:
            pass

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Mobile User Agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ.get("CHROME_BIN")
    
    return webdriver.Chrome(options=chrome_options)

def perform_login(driver):
    print("🔑 Detect Login Page. Attempting to Log In...")
    
    try:
        wait = WebDriverWait(driver, 10)
        
        # 1. Find Phone Field (Looking for input type 'tel' or name containing 'phone')
        phone_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='tel' or contains(@name, 'phone') or contains(@placeholder, 'Phone')]")))
        phone_input.clear()
        phone_input.send_keys(LOGIN_PHONE)
        print("   - Phone entered.")
        
        # 2. Find Password Field
        pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_input.clear()
        pass_input.send_keys(LOGIN_PASSWORD)
        print("   - Password entered.")
        
        # 3. Click Login Button
        # Looking for a button that says "Log" or "Sign" inside it
        login_btn = driver.find_element(By.XPATH, "//button[contains(., 'Log') or contains(., 'Sign')]")
        driver.execute_script("arguments[0].click();", login_btn)
        print("   - Login button clicked.")
        
        time.sleep(10) # Wait for redirect
        print(f"   - Page title after login: {driver.title}")
        return True
        
    except Exception as e:
        print(f"❌ Login Failed: {e}")
        return False

def find_game_grid(driver):
    """
    Scans for Keno grid in main page and iframes.
    """
    print("🔎 Scanning for Keno grid (Numbers 1-80)...")
    
    # 1. Check Main Page
    cls = detect_grid_logic(driver)
    if cls: return cls

    # 2. Check Iframes
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"  - Found {len(frames)} frames. Checking inside them...")
    
    for i, frame in enumerate(frames):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            cls = detect_grid_logic(driver)
            if cls:
                print(f"✅ FOUND GAME inside Frame #{i+1}!")
                return cls
        except:
            continue
            
    return None

def detect_grid_logic(driver):
    try:
        # Search for text '80'
        potential_80s = driver.find_elements(By.XPATH, "//*[text()='80']")
        for el in potential_80s:
            class_name = el.get_attribute("class")
            if not class_name: continue
            base_class = class_name.split()[0]
            siblings = driver.find_elements(By.CLASS_NAME, base_class)
            if 70 <= len(siblings) <= 90:
                return base_class
    except:
        pass
    return None

def main():
    if not LOGIN_PHONE or not LOGIN_PASSWORD:
        print("❌ Error: Missing LOGIN_PHONE or LOGIN_PASSWORD in Render Environment.")
        return

    driver = setup_driver()
    print("🚀 Bot Started...")
    
    try:
        driver.get(GAME_URL)
        time.sleep(5)
        print(f"📄 Initial Title: {driver.title}")
        
        # Check if we are on the Sign In page
        if "Sign in" in driver.title or "Login" in driver.title:
            success = perform_login(driver)
            if success:
                # Reload the game URL to be sure we are in the right place
                driver.get(GAME_URL)
                time.sleep(10)
            else:
                send_telegram("❌ Login failed. Check logs.")
                return

        # Now look for the game
        keno_class = find_game_grid(driver)
        
        if not keno_class:
            send_telegram(f"❌ Failed to find numbers. Current Title: {driver.title}")
            return

        msg = f"✅ LOCKED ON! Tracking numbers via class: '{keno_class}'"
        print(msg)
        send_telegram(msg)
        
        last_alert_numbers = []
        
        while True:
            # JavaScript to find flashing items
            script = f"""
            var changed_numbers = [];
            var elements = document.getElementsByClassName('{keno_class}');
            for (var i = 0; i < elements.length; i++) {{
                if (elements[i].className.length > '{keno_class}'.length + 2) {{
                    changed_numbers.push(elements[i].innerText);
                }}
            }}
            return changed_numbers;
            """
            
            try:
                active_numbers = driver.execute_script(script)
                if active_numbers:
                    active_numbers.sort()
                    if active_numbers != last_alert_numbers:
                        clean_nums = [n for n in active_numbers if n.strip().isdigit()]
                        if clean_nums:
                            alert_msg = f"⚡ FLASH: {', '.join(clean_nums)}"
                            print(alert_msg)
                            send_telegram(alert_msg)
                            last_alert_numbers = active_numbers
            except:
                break
                
            time.sleep(0.1)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
