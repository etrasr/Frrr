import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LOGIN_PHONE = os.environ.get("LOGIN_PHONE")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD")

# We start at the Casino page. The site will redirect to Login if needed.
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
    # Mobile User Agent (Matches your screenshot)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36")
    
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ.get("CHROME_BIN")
    
    return webdriver.Chrome(options=chrome_options)

def perform_login(driver):
    print("🔑 Detect Login Page. Attempting to Log In...")
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # 1. Enter Phone
        print("   - Typing phone...")
        phone_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@type='tel' or contains(@name, 'phone') or contains(@placeholder, 'Phone')]")))
        phone_input.clear()
        phone_input.send_keys(LOGIN_PHONE)
        time.sleep(1)
        
        # 2. Enter Password
        print("   - Typing password...")
        pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_input.clear()
        pass_input.send_keys(LOGIN_PASSWORD)
        time.sleep(1)
        
        # 3. Find and Click LOGIN Button
        print("   - looking for LOGIN button...")
        
        # Strategy: Find the yellow button with text 'LOGIN'
        try:
            login_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'LOGIN')]")
            
            # SCROLL TO BUTTON (Crucial for mobile view)
            driver.execute_script("arguments[0].scrollIntoView(true);", login_btn)
            time.sleep(1)
            
            # ATTEMPT 1: JavaScript Click (Best for hidden/overlay buttons)
            print("   - Attempting JS Click...")
            driver.execute_script("arguments[0].click();", login_btn)
            
            # Wait to see if URL changes
            time.sleep(5)
            
            # ATTEMPT 2: If we are still on the login page, try pressing ENTER on the password field
            if "auth" in driver.current_url or "Sign" in driver.title:
                print("   - JS Click didn't redirect. Trying ENTER key...")
                pass_input.send_keys(Keys.RETURN)
                
        except Exception as e:
            print(f"   - Button click issue: {e}. Trying ENTER key fallback.")
            pass_input.send_keys(Keys.RETURN)
            
        
        # 4. Wait for Redirect (Longer wait)
        print("   - Waiting 15s for redirect...")
        time.sleep(15)
        
        # 5. Verification
        if "Sign" in driver.title or "auth" in driver.current_url:
            print("❌ STUCK ON LOGIN PAGE.")
            
            # CAPTURE THE ERROR MESSAGE FROM SCREEN
            body_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Look for common error keywords
            error_keywords = ["Invalid", "Incorrect", "match", "found", "required"]
            found_error = "Unknown Error"
            for line in body_text.split('\n'):
                for key in error_keywords:
                    if key in line:
                        found_error = line
                        break
            
            print(f"   - Screen says: {found_error}")
            send_telegram(f"❌ Login Failed. Site says: {found_error}")
            return False
            
        print(f"   - Success! New Title: {driver.title}")
        return True
        
    except Exception as e:
        print(f"❌ Critical Login Error: {e}")
        return False

def find_game_grid(driver):
    print("🔎 Scanning for Keno grid...")
    
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
        # Search for text '80' inside a container
        potential_80s = driver.find_elements(By.XPATH, "//*[text()='80']")
        for el in potential_80s:
            class_name = el.get_attribute("class")
            if not class_name: continue
            base_class = class_name.split()[0]
            siblings = driver.find_elements(By.CLASS_NAME, base_class)
            # Keno has 80 numbers
            if 70 <= len(siblings) <= 90:
                return base_class
    except:
        pass
    return None

def main():
    if not LOGIN_PHONE or not LOGIN_PASSWORD:
        print("❌ Error: Missing credentials in Render Environment.")
        return

    driver = setup_driver()
    print("🚀 Bot Started (Deep Debug Mode)...")
    
    try:
        driver.get(GAME_URL)
        time.sleep(5)
        print(f"📄 Initial Page: {driver.title}")
        
        # LOGIN LOGIC
        # We check URL or Title to see if we were redirected to login
        if "Sign" in driver.title or "auth" in driver.current_url:
            success = perform_login(driver)
            if not success:
                driver.quit()
                return
            
            # Force reload the game URL to ensure we leave the auth page
            print("🔄 Force-loading Game URL...")
            driver.get(GAME_URL)
            time.sleep(15)

        # FIND GRID
        keno_class = find_game_grid(driver)
        
        if not keno_class:
            send_telegram(f"❌ Login seemed okay, but still can't find numbers. I am at: {driver.title}")
            return

        msg = f"✅ LOCKED ON! Tracking via class: '{keno_class}'"
        print(msg)
        send_telegram(msg)
        
        last_alert_numbers = []
        
        while True:
            script = f"""
            var changed_numbers = [];
            var elements = document.getElementsByClassName('{keno_class}');
            for (var i = 0; i < elements.length; i++) {{
                // If class name is longer, it implies a color change modifier
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
